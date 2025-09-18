"""
MovieLens 25M loader for PostgreSQL.

This script ingests MovieLens 25M `movies.csv` and `ratings.csv` into a
normalized PostgreSQL schema defined in `db/schema.sql`.

Features:
- Chunked ingestion for the large `ratings.csv` file (25M rows)
- Idempotent upserts for `movies`, `users`, and `interactions`
- Simple genre parsing and title year extraction
- Configurable via CLI flags or environment variables

Environment variables:
- DATABASE_URL: PostgreSQL connection string, e.g. postgres://user:pass@localhost:5432/movies

Usage:
    python data/load_movielens.py \
        --movies_csv /path/to/ml-25m/movies.csv \
        --ratings_csv /path/to/ml-25m/ratings.csv \
        --batch_size 50000
"""

import argparse
import csv
import logging
import os
import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import execute_values


LOGGER = logging.getLogger("movielens_loader")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def parse_year_from_title(title: str) -> Optional[int]:
    """Extracts year from a title like "Toy Story (1995)" if present."""
    if not title:
        return None
    match = re.search(r"\((\d{4})\)\s*$", title)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def parse_genres(genres_field: str) -> List[str]:
    if not genres_field or genres_field == "(no genres listed)":
        return []
    return [g.strip() for g in genres_field.split("|") if g.strip()]


def ensure_connection(db_url: str):
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    return conn


def upsert_movies(conn, movies_csv_path: str) -> int:
    """Upsert movies from movies.csv. Returns number of rows processed."""
    LOGGER.info("Loading movies from %s", movies_csv_path)
    insert_sql = (
        """
        INSERT INTO movies (movie_id, title, year, genres)
        VALUES %s
        ON CONFLICT (movie_id) DO UPDATE
        SET title = EXCLUDED.title,
            year = EXCLUDED.year,
            genres = EXCLUDED.genres,
            updated_at = now()
        """
    )

    rows: List[Tuple[int, str, Optional[int], List[str]]] = []
    processed = 0
    with open(movies_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            try:
                movie_id = int(rec["movieId"])
            except Exception:
                continue
            title = rec.get("title", "").strip()
            year = parse_year_from_title(title)
            genres = parse_genres(rec.get("genres", ""))
            rows.append((movie_id, title, year, genres))
            processed += 1

    if not rows:
        LOGGER.warning("No movies parsed from %s", movies_csv_path)
        return 0

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, rows, page_size=10000)
    conn.commit()
    LOGGER.info("Upserted %d movies", processed)
    return processed


def upsert_users(conn, user_ids: Sequence[int]) -> int:
    if not user_ids:
        return 0
    values = [(uid,) for uid in user_ids]
    insert_sql = (
        """
        INSERT INTO users (user_id)
        VALUES %s
        ON CONFLICT (user_id) DO NOTHING
        """
    )
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values, page_size=10000)
    return len(user_ids)


def iter_ratings_batches(ratings_csv_path: str, batch_size: int) -> Iterable[List[Tuple[int, int, float, Optional[datetime]]]]:
    """Yield batches of (user_id, movie_id, rating, interacted_at) from ratings.csv."""
    batch: List[Tuple[int, int, float, Optional[datetime]]] = []
    with open(ratings_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            try:
                user_id = int(rec["userId"])
                movie_id = int(rec["movieId"])
                rating = float(rec["rating"])
                ts_raw = rec.get("timestamp")
                interacted_at = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc) if ts_raw else None
            except Exception:
                continue
            batch.append((user_id, movie_id, rating, interacted_at))
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def upsert_interactions(conn, interactions: Sequence[Tuple[int, int, float, Optional[datetime]]]) -> None:
    insert_sql = (
        """
        INSERT INTO interactions (user_id, movie_id, rating, interacted_at, interaction_type, weight)
        VALUES %s
        ON CONFLICT (user_id, movie_id) DO UPDATE
        SET rating = EXCLUDED.rating,
            interacted_at = COALESCE(EXCLUDED.interacted_at, interactions.interacted_at),
            interaction_type = EXCLUDED.interaction_type,
            weight = EXCLUDED.weight
        """
    )
    values = [
        (user_id, movie_id, rating, interacted_at, "rating", float(rating))
        for (user_id, movie_id, rating, interacted_at) in interactions
    ]
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values, page_size=10000)


def load_movielens(db_url: str, movies_csv: str, ratings_csv: str, batch_size: int = 50000) -> None:
    conn = ensure_connection(db_url)
    try:
        total_movies = upsert_movies(conn, movies_csv)
        LOGGER.info("Movies upserted: %d", total_movies)

        total_users = 0
        total_interactions = 0

        LOGGER.info("Loading ratings from %s in batches of %d", ratings_csv, batch_size)
        for idx, batch in enumerate(iter_ratings_batches(ratings_csv, batch_size), start=1):
            user_ids = sorted({u for (u, _m, _r, _t) in batch})
            upserted_users = upsert_users(conn, user_ids)

            upsert_interactions(conn, batch)
            conn.commit()

            total_users += upserted_users
            total_interactions += len(batch)
            if idx % 10 == 0:
                LOGGER.info("Processed %d batches (~%d interactions)", idx, total_interactions)

        LOGGER.info(
            "Finished loading ratings. Users seen: %d, Interactions upserted: %d",
            total_users,
            total_interactions,
        )
    except Exception:
        conn.rollback()
        LOGGER.exception("Error during ingestion; rolled back last transaction")
        raise
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load MovieLens 25M into PostgreSQL")
    parser.add_argument("--movies_csv", required=True, help="Path to movies.csv from ml-25m")
    parser.add_argument("--ratings_csv", required=True, help="Path to ratings.csv from ml-25m")
    parser.add_argument("--database_url", default=os.environ.get("DATABASE_URL"), help="PostgreSQL URL")
    parser.add_argument("--batch_size", type=int, default=50000, help="Batch size for ratings ingestion")
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database_url or env DATABASE_URL must be provided")
    return args


def main() -> None:
    setup_logging()
    args = parse_args()
    LOGGER.info("Starting MovieLens ingestion")
    load_movielens(
        db_url=args.database_url,
        movies_csv=args.movies_csv,
        ratings_csv=args.ratings_csv,
        batch_size=args.batch_size,
    )
    LOGGER.info("Ingestion completed successfully")


if __name__ == "__main__":
    main()


