"""
Centralized configuration helpers for the Movie Recommendation system.

Reads environment variables and exposes small utility helpers used across scripts.

Environment variables:
- DATABASE_URL: PostgreSQL connection string
- TMDB_API_KEY: API key for The Movie Database (TMDB)
"""

import os
from typing import Optional


def get_database_url() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set in environment")
    return db_url


def get_tmdb_api_key(required: bool = True) -> Optional[str]:
    api_key = os.environ.get("TMDB_API_KEY")
    if required and not api_key:
        raise RuntimeError("TMDB_API_KEY is not set in environment")
    return api_key


def get_embedding_dim(default: int = 64) -> int:
    try:
        return int(os.environ.get("EMBEDDING_DIM", str(default)))
    except Exception:
        return default


