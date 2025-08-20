"""
FastAPI application serving movie recommendations + simple write endpoints.

Endpoints:
- GET  /                      -> redirects to /docs
- GET  /healthz               -> DB health check
- POST /users                 -> create/ensure a user_id exists
- POST /interactions          -> upsert a user->movie interaction (rating/weight)
- GET  /interactions/{user_id} -> list interactions for a user (paged)
- GET  /movies/search         -> search movies by title (returns poster URLs)
- GET  /similar/{movie_id}    -> item-to-item "more like this" using pgvector
- GET  /recommendations/{user_id} -> personalized recs (user-based)
- GET  /trending              -> popularity fallback
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import logging
import os
from typing import Any, List, Optional, Tuple

import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

LOGGER = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

# --- DB config ---
try:
    from config.settings import DATABASE_URL as CFG_DATABASE_URL  # type: ignore
    DATABASE_URL = CFG_DATABASE_URL or os.environ.get("DATABASE_URL")
except Exception:
    DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

def _normalize_pg_dsn(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url.split("postgresql+psycopg://", 1)[1]
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url

DSN = _normalize_pg_dsn(DATABASE_URL)

# vector metric selection
VECTOR_METRIC = os.environ.get("VECTOR_METRIC", "cosine").lower().strip()
DIST_OP = "<=>" if VECTOR_METRIC == "cosine" else "<->"

# poster helpers
TMDB_IMAGE_BASE = os.environ.get("TMDB_IMAGE_BASE", "https://image.tmdb.org/t/p/w342")
POSTER_PLACEHOLDER = os.environ.get("POSTER_PLACEHOLDER", "https://placehold.co/342x513?text=No+Poster")

app = FastAPI(title="Movie Recommender API", version="0.5.0")

def get_conn():
    return psycopg2.connect(DSN)

# --- Models ---
class Movie(BaseModel):
    movie_id: int
    title: str
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    genres: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    user_id: int
    items: List[Movie]

class CreateUserPayload(BaseModel):
    user_id: int = Field(..., ge=1)

class InteractionPayload(BaseModel):
    user_id: int
    movie_id: int
    rating: Optional[float] = None
    weight: Optional[float] = None
    interaction_type: Optional[str] = "rating"

class InteractionRow(BaseModel):
    user_id: int
    movie_id: int
    rating: float | None = None
    weight: float | None = None
    interaction_type: str
    interacted_at: str | None = None

class InteractionsResponse(BaseModel):
    user_id: int
    count: int
    items: list[InteractionRow]

# --- helpers ---
def _join_poster(p: Optional[str]) -> str:
    if not p:
        return POSTER_PLACEHOLDER
    if p.startswith("http://") or p.startswith("https://"):
        return p
    return f"{TMDB_IMAGE_BASE}{p}"

def _movie_from_row(row: Tuple[Any, ...]) -> Movie:
    mid, title, year, overview, poster, genres = row
    title = title or "Unknown Title"
    overview = overview or ""
    genres = list(genres) if genres else None
    poster_full = _join_poster(poster)
    return Movie(
        movie_id=int(mid),
        title=str(title),
        year=int(year) if year is not None else None,
        overview=str(overview),
        poster_path=poster_full,
        genres=genres,
    )

def _avg_user_vector_from_seen(conn, user_id: int) -> Optional[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT AVG(embedding)
            FROM item_embeddings
            WHERE movie_id IN (SELECT movie_id FROM interactions WHERE user_id = %s)
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row or row[0] is None:
            return None
        cur.execute("SELECT %s::vector::text", (row[0],))
        return cur.fetchone()[0]

# --- routes ---
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/healthz")
def healthz():
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            _ = cur.fetchone()
        return {"ok": True}
    except Exception as e:
        LOGGER.exception("healthz failed")
        return {"ok": False, "error": str(e)}

@app.post("/users", tags=["Users"])
def create_user(payload: CreateUserPayload):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (payload.user_id,))
            conn.commit()
        return {"ok": True, "user_id": payload.user_id}
    except Exception:
        LOGGER.exception("Failed to create user")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/interactions", tags=["Interactions"])
def upsert_interaction(payload: InteractionPayload):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (payload.user_id,))
            cur.execute("SELECT 1 FROM movies WHERE movie_id = %s", (payload.movie_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=400, detail=f"movie_id {payload.movie_id} not found")

            cur.execute(
                """
                INSERT INTO interactions (user_id, movie_id, rating, weight, interaction_type, interacted_at)
                VALUES (
                    %s,
                    %s,
                    %s,
                    COALESCE(%s, CASE WHEN %s IS NULL THEN 1.0 ELSE NULL END),
                    %s,
                    now()
                )
                ON CONFLICT (user_id, movie_id) DO UPDATE
                SET rating = EXCLUDED.rating,
                    weight = EXCLUDED.weight,
                    interaction_type = EXCLUDED.interaction_type,
                    interacted_at = EXCLUDED.interacted_at
                """,
                (
                    payload.user_id,
                    payload.movie_id,
                    payload.rating,
                    payload.weight,
                    payload.rating,
                    payload.interaction_type,
                ),
            )
            conn.commit()
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to upsert interaction")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/interactions/{user_id}", response_model=InteractionsResponse, tags=["Interactions"])
def get_interactions(user_id: int, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"user_id {user_id} not found")

            cur.execute("SELECT COUNT(*) FROM interactions WHERE user_id = %s", (user_id,))
            total = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT user_id, movie_id, rating, weight, interaction_type, interacted_at
                FROM interactions
                WHERE user_id = %s
                ORDER BY interacted_at DESC NULLS LAST, movie_id
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            items = [
                InteractionRow(
                    user_id=int(u),
                    movie_id=int(m),
                    rating=float(rating) if rating is not None else None,
                    weight=float(weight) if weight is not None else None,
                    interaction_type=str(itype or "rating"),
                    interacted_at=(ts.isoformat() if ts is not None else None),
                )
                for (u, m, rating, weight, itype, ts) in cur.fetchall()
            ]
            return InteractionsResponse(user_id=user_id, count=total, items=items)
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to fetch interactions")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/movies/search", tags=["Movies"])
def search_movies(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=100)):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT movie_id, title, year, overview, poster_path, genres
                FROM movies
                WHERE lower(title) LIKE lower(%s)
                ORDER BY year NULLS LAST, title
                LIMIT %s
                """,
                (f"%{q}%", limit),
            )
            return [_movie_from_row(r) for r in cur.fetchall()]
    except Exception:
        LOGGER.exception("Failed to search movies")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/similar/{movie_id}", response_model=List[Movie], tags=["Similar"])
def similar(movie_id: int, limit: int = Query(10, ge=1, le=100)):
    """
    Item-to-item recommendations using pgvector nearest neighbors.
    """
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # ensure we have an embedding for this movie
            cur.execute("SELECT embedding::text FROM item_embeddings WHERE movie_id = %s", (movie_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Embedding for movie not found. Train the model first.")

            cur.execute(
                f"""
                WITH target AS (SELECT %s::vector AS v)
                SELECT m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                FROM item_embeddings ie
                JOIN target ON true
                JOIN movies m ON m.movie_id = ie.movie_id
                WHERE ie.movie_id <> %s
                ORDER BY ie.embedding {DIST_OP} target.v
                LIMIT %s
                """,
                (row[0], movie_id, limit),
            )
            return [_movie_from_row(r) for r in cur.fetchall()]
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to fetch similar items")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/recommendations/{user_id}", response_model=RecommendationResponse, tags=["Recommendations"])
def recommendations(user_id: int, limit: int = Query(10, ge=1, le=100)):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT embedding::text FROM public.user_embeddings WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            user_vec_text: Optional[str] = row[0] if row else None

            if user_vec_text is None:
                user_vec_text = _avg_user_vector_from_seen(conn, user_id)
                if user_vec_text is None:
                    cur.execute(
                        """
                        SELECT m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                        FROM public.movies m
                        JOIN public.interactions i ON i.movie_id = m.movie_id
                        GROUP BY m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                        ORDER BY COUNT(*) DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    items = [_movie_from_row(r) for r in cur.fetchall()]
                    return RecommendationResponse(user_id=user_id, items=items)

            cur.execute("SELECT movie_id FROM public.interactions WHERE user_id = %s", (user_id,))
            seen_ids = [int(r[0]) for r in cur.fetchall()]

            cur.execute(
                f"""
                WITH user_vec AS (SELECT %s::vector AS v)
                SELECT m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                FROM public.item_embeddings ie
                JOIN user_vec ON true
                JOIN public.movies m ON m.movie_id = ie.movie_id
                WHERE NOT (ie.movie_id = ANY(%s))
                ORDER BY ie.embedding {DIST_OP} user_vec.v
                LIMIT %s
                """,
                (user_vec_text, seen_ids, limit),
            )
            items = [_movie_from_row(r) for r in cur.fetchall()]
            return RecommendationResponse(user_id=user_id, items=items)

    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to fetch recommendations")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/trending", response_model=List[Movie], tags=["Trending"])
def trending(days: int = Query(7, ge=1, le=30), limit: int = Query(20, ge=1, le=100)):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                FROM public.interactions i
                JOIN public.movies m ON m.movie_id = i.movie_id
                WHERE i.interacted_at >= now() - (%s || ' days')::interval
                GROUP BY m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (days, limit),
            )
            return [_movie_from_row(r) for r in cur.fetchall()]
    except Exception:
        LOGGER.exception("Failed to fetch trending movies")
        raise HTTPException(status_code=500, detail="Internal server error")
