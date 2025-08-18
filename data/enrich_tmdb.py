"""
Enrich movie metadata using TMDB API.

For each movie in the `movies` table, query TMDB by title and year, then update
`tmdb_id`, `overview`, `poster_path`, and `genres` if available.

Usage:
    python data/enrich_tmdb.py --limit 5000 --start_offset 0

Environment:
- DATABASE_URL
- TMDB_API_KEY
"""

import argparse
import logging
from typing import Dict, List, Optional, Tuple

import psycopg2
import requests

from config.settings import get_database_url, get_tmdb_api_key


LOGGER = logging.getLogger("enrich_tmdb")
TMDB_BASE = "https://api.themoviedb.org/3"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def ensure_connection():
    return psycopg2.connect(get_database_url())


def fetch_movies_to_enrich(conn, limit: int, offset: int) -> List[Tuple[int, str, Optional[int]]]:
    sql = (
        """
        SELECT movie_id, title, year
        FROM movies
        WHERE overview IS NULL OR poster_path IS NULL OR tmdb_id IS NULL
        ORDER BY movie_id
        LIMIT %s OFFSET %s
        """
    )
    with conn.cursor() as cur:
        cur.execute(sql, (limit, offset))
        return [(int(mid), str(title), int(year) if year is not None else None) for (mid, title, year) in cur.fetchall()]


def tmdb_search(api_key: str, title: str, year: Optional[int]) -> Optional[Dict]:
    params = {"api_key": api_key, "query": title}
    if year:
        params["year"] = year
    try:
        resp = requests.get(f"{TMDB_BASE}/search/movie", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        return results[0] if results else None
    except Exception:
        LOGGER.exception("TMDB search failed for title=%s year=%s", title, year)
        return None


def tmdb_movie_details(api_key: str, tmdb_id: int) -> Optional[Dict]:
    params = {"api_key": api_key, "append_to_response": "credits"}
    try:
        resp = requests.get(f"{TMDB_BASE}/movie/{tmdb_id}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        LOGGER.exception("TMDB details failed for tmdb_id=%s", tmdb_id)
        return None


def update_movie(conn, movie_id: int, tmdb_id: Optional[int], overview: Optional[str], poster_path: Optional[str], genres: Optional[List[str]]) -> None:
    sql = (
        """
        UPDATE movies
        SET tmdb_id = COALESCE(%s, tmdb_id),
            overview = COALESCE(%s, overview),
            poster_path = COALESCE(%s, poster_path),
            genres = CASE WHEN %s IS NOT NULL AND array_length(%s, 1) > 0 THEN %s ELSE genres END,
            updated_at = now()
        WHERE movie_id = %s
        """
    )
    with conn.cursor() as cur:
        cur.execute(sql, (tmdb_id, overview, poster_path, genres, genres, genres, movie_id))


def enrich_batch(conn, movies: List[Tuple[int, str, Optional[int]]], api_key: str) -> int:
    updated = 0
    for movie_id, title, year in movies:
        search_res = tmdb_search(api_key, title, year)
        if not search_res:
            continue
        tmdb_id = int(search_res.get("id"))
        details = tmdb_movie_details(api_key, tmdb_id)
        if not details:
            continue
        overview = details.get("overview")
        poster_path = details.get("poster_path")
        genres = [g.get("name") for g in details.get("genres", []) if g.get("name")]
        update_movie(conn, movie_id, tmdb_id, overview, poster_path, genres)
        updated += 1
    conn.commit()
    return updated


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Enrich movies with TMDB metadata")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--start_offset", type=int, default=0)
    args = parser.parse_args()

    api_key = get_tmdb_api_key(required=True)
    conn = ensure_connection()
    try:
        offset = args.start_offset
        total_updated = 0
        while True:
            movies = fetch_movies_to_enrich(conn, args.limit, offset)
            if not movies:
                break
            LOGGER.info("Enriching %d movies (offset=%d)", len(movies), offset)
            updated = enrich_batch(conn, movies, api_key)  # type: ignore[arg-type]
            total_updated += updated
            LOGGER.info("Updated %d movies in this batch (total=%d)", updated, total_updated)
            offset += args.limit
    except Exception:
        conn.rollback()
        LOGGER.exception("TMDB enrichment failed; rolled back last transaction")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()


