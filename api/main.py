"""
FastAPI application serving movie recommendations.

Endpoints:
- GET /recommendations/{user_id}?limit=10: Personalized recs using cosine similarity over pgvector
- GET /trending?days=7&limit=20: Top watched by interactions in recent days
"""

import os
import logging
from typing import List, Optional

import numpy as np
import psycopg2
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


LOGGER = logging.getLogger("api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

app = FastAPI(title="Movie Recommender API")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


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


@app.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def recommendations(user_id: int, limit: int = Query(10, ge=1, le=100)):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT embedding FROM user_embeddings WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User embedding not found. Train the model first.")
            user_vec_str = row[0]
            # Use pgvector cosine distance; exclude items the user already interacted with
            cur.execute(
                """
                WITH user_vec AS (
                    SELECT %s::vector AS v
                ),
                seen AS (
                    SELECT movie_id FROM interactions WHERE user_id = %s
                )
                SELECT m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                FROM item_embeddings ie
                JOIN user_vec ON true
                JOIN movies m ON m.movie_id = ie.movie_id
                WHERE ie.movie_id NOT IN (SELECT movie_id FROM seen)
                ORDER BY (1 - (ie.embedding <#> user_vec.v)) DESC
                LIMIT %s
                """,
                (user_vec_str, user_id, limit),
            )
            items = [
                Movie(
                    movie_id=int(mid),
                    title=title,
                    year=int(year) if year is not None else None,
                    overview=overview,
                    poster_path=poster,
                    genres=list(genres) if genres else None,
                )
                for (mid, title, year, overview, poster, genres) in cur.fetchall()
            ]
            return RecommendationResponse(user_id=user_id, items=items)
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("Failed to fetch recommendations")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/trending", response_model=List[Movie])
def trending(days: int = Query(7, ge=1, le=30), limit: int = Query(20, ge=1, le=100)):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                FROM interactions i
                JOIN movies m ON m.movie_id = i.movie_id
                WHERE i.interacted_at >= now() - (%s || ' days')::interval
                GROUP BY m.movie_id, m.title, m.year, m.overview, m.poster_path, m.genres
                ORDER BY COUNT(*) DESC
                LIMIT %s
                """,
                (days, limit),
            )
            return [
                Movie(
                    movie_id=int(mid),
                    title=title,
                    year=int(year) if year is not None else None,
                    overview=overview,
                    poster_path=poster,
                    genres=list(genres) if genres else None,
                )
                for (mid, title, year, overview, poster, genres) in cur.fetchall()
            ]
    except Exception:
        LOGGER.exception("Failed to fetch trending movies")
        raise HTTPException(status_code=500, detail="Internal server error")


