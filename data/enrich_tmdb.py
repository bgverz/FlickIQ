"""
Backfill/enrich movies from TMDB.

Features:
- Cleans MovieLens-style titles before search:
  - strips trailing year " (1995)"
  - removes parenthetical bits "(a.k.a. ...)"
  - normalizes trailing articles: "Few Good Men, A" -> "A Few Good Men"
- Retries search with and without year
- After a search hit, fetches full details via /movie/{id}
- Fills poster_path, overview, year, genres, tmdb_id, imdb_id when missing
- AUTO-ADAPTS imdb_id to your DB column type:
  - if movies.imdb_id is BIGINT: stores numeric part of "tt..."
  - if TEXT/VARCHAR: stores full "tt..." string

Usage:
  set -a; source .env; set +a
  pip install requests

  # dry run
  python -m data.enrich_tmdb --limit 50 --only-missing --dry-run

  # update DB
  python -m data.enrich_tmdb --limit 1000 --only-missing
"""
from __future__ import annotations

import argparse
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_KEY = os.environ.get("TMDB_API_KEY")
if not TMDB_KEY:
    raise SystemExit("TMDB_API_KEY not set")

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise SystemExit("DATABASE_URL not set")
if DB_URL.startswith("postgresql+psycopg://"):
    DB_URL = "postgresql://" + DB_URL.split("postgresql+psycopg://", 1)[1]
if DB_URL.startswith("postgres://"):
    DB_URL = "postgresql://" + DB_URL[len("postgres://"):]

BASE = "https://api.themoviedb.org/3"
SESSION = requests.Session()

def tmdb_get(path: str, **params) -> Dict[str, Any]:
    params = {"api_key": TMDB_KEY, "include_adult": "false", "language": "en-US", **params}
    r = SESSION.get(f"{BASE}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def tmdb_movie_details(tmdb_id: int) -> Optional[Dict[str, Any]]:
    try:
        return tmdb_get(f"/movie/{tmdb_id}")
    except requests.HTTPError:
        return None

# ---------- Title normalization (MovieLens -> TMDB-friendly) ----------
def strip_year_suffix(title: str) -> str:
    return re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()

def remove_parentheticals(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", title).strip()

def untail_article(title: str) -> str:
    m = re.match(r"^(.*),\s*(A|An|The)$", title.strip(), flags=re.IGNORECASE)
    if not m:
        return title.strip()
    core, art = m.group(1).strip(), m.group(2).strip()
    return f"{art} {core}"

def normalize_title(title: str) -> str:
    t = strip_year_suffix(title or "")
    t = remove_parentheticals(t)
    t = untail_article(t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t

def tmdb_search_best(title: str, year: Optional[int]) -> Optional[Dict[str, Any]]:
    """
    Try multiple cleaned variants, with and without year.
    Return full movie details (not just the search hit), or None.
    """
    candidates: List[Tuple[str, Optional[int]]] = []
    base = normalize_title(title)
    candidates.append((base, year))
    candidates.append((base, None))

    if re.search(r",\s*(A|An|The)$", base, flags=re.IGNORECASE):
        swapped = untail_article(base)
        if swapped != base:
            candidates.append((swapped, year))
            candidates.append((swapped, None))

    tried = set()
    for t, y in candidates:
        key = (t.lower(), y)
        if key in tried:
            continue
        tried.add(key)
        try:
            params = {"query": t}
            if y:
                params["year"] = y
            data = tmdb_get("/search/movie", **params)
            results = data.get("results") or []
            if results:
                details = tmdb_movie_details(int(results[0]["id"]))
                if details:
                    return details
        except requests.HTTPError:
            continue
    return None

def extract_fields(j: Dict[str, Any]) -> Dict[str, Any]:
    if not j:
        return {}
    release_date = j.get("release_date") or ""
    year = int(release_date.split("-")[0]) if release_date[:4].isdigit() else None
    genres = [g.get("name") for g in (j.get("genres") or []) if g.get("name")]
    return {
        "tmdb_id": j.get("id"),
        "imdb_id": j.get("imdb_id"),  # "tt0114709" style
        "poster_path": j.get("poster_path"),
        "overview": j.get("overview"),
        "year": year,
        "genres": genres if genres else None,
        "title": j.get("title") or j.get("original_title"),
    }

def should_update(existing: Any, new_val: Any, overwrite: bool) -> bool:
    if overwrite:
        return new_val is not None
    return (existing in (None, "", [])) and (new_val is not None)

# ---------- IMDb column type detection & coercion ----------
def get_imdb_column_type(conn) -> str:
    """
    Returns the data_type string for movies.imdb_id (e.g., 'bigint', 'text', 'character varying')
    Defaults to 'text' if not found.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'movies'
              AND column_name = 'imdb_id'
            """
        )
        row = cur.fetchone()
    return (row[0].lower() if row and row[0] else "text")

def coerce_imdb_value(raw: Any, target_type: str) -> Optional[Any]:
    """
    If target_type is bigint/integer/numeric, convert "tt12345" -> 12345 (int).
    If text/varchar, keep as string "tt12345".
    """
    if raw is None:
        return None
    if target_type in ("bigint", "integer", "numeric", "decimal", "smallint"):
        if isinstance(raw, str) and raw.startswith("tt"):
            num = raw[2:]
            return int(num) if num.isdigit() else None
        if isinstance(raw, (int,)):
            return raw
        # Try to parse any other string
        try:
            return int(str(raw))
        except Exception:
            return None
    # text-ish
    return str(raw)

# ---------- Main ----------
def main() -> None:
    ap = argparse.ArgumentParser(description="Enrich movies from TMDB")
    ap.add_argument("--limit", type=int, default=500, help="Max rows to process")
    ap.add_argument("--only-missing", action="store_true", help="Only rows missing poster/overview/year/genres")
    ap.add_argument("--overwrite-posters", action="store_true")
    ap.add_argument("--overwrite-overview", action="store_true")
    ap.add_argument("--overwrite-year", action="store_true")
    ap.add_argument("--overwrite-genres", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.25, help="Delay between TMDB calls")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    where = ""
    if args.only_missing:
        where = (
            "WHERE (poster_path IS NULL OR overview IS NULL OR year IS NULL OR array_length(genres,1) IS NULL)"
        )

    sql = f"""
        SELECT movie_id, title, year, tmdb_id, imdb_id, poster_path, overview, genres
        FROM movies
        {where}
        ORDER BY movie_id
        LIMIT %s
    """

    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    updated = 0
    checked = 0

    try:
        imdb_type = get_imdb_column_type(conn)
        print(f"Detected movies.imdb_id type: {imdb_type}")

        with conn.cursor() as cur:
            cur.execute(sql, (args.limit,))
            rows: List[Tuple[Any, ...]] = cur.fetchall()
            print(f"Fetched {len(rows)} movie rows to consider")

            for (movie_id, title, year, tmdb_id, imdb_id, poster_path, overview, genres) in rows:
                checked += 1

                # Prefer tmdb_id; otherwise robust search
                data = tmdb_movie_details(int(tmdb_id)) if tmdb_id else None
                if data is None:
                    data = tmdb_search_best(title or "", int(year) if year else None)

                if not data:
                    print(f"- skip {movie_id} '{title}': no TMDB result")
                    time.sleep(args.sleep)
                    continue

                fields = extract_fields(data)

                # Build update sets
                sets: List[str] = []
                vals: List[Any] = []

                if should_update(poster_path, fields.get("poster_path"), args.overwrite_posters):
                    sets.append("poster_path = %s")
                    vals.append(fields.get("poster_path"))

                if should_update(overview, fields.get("overview"), args.overwrite_overview):
                    sets.append("overview = %s")
                    vals.append(fields.get("overview"))

                if should_update(year, fields.get("year"), args.overwrite_year):
                    sets.append("year = %s")
                    vals.append(fields.get("year"))

                if should_update(genres, fields.get("genres"), args.overwrite_genres):
                    sets.append("genres = %s")
                    vals.append(fields.get("genres"))

                # Always fill tmdb_id if missing and we found it
                if should_update(tmdb_id, fields.get("tmdb_id"), overwrite=False):
                    sets.append("tmdb_id = %s")
                    vals.append(fields.get("tmdb_id"))

                # imdb_id: adapt to column type
                imdb_raw = fields.get("imdb_id")
                imdb_coerced = coerce_imdb_value(imdb_raw, imdb_type)
                if should_update(imdb_id, imdb_coerced, overwrite=False):
                    sets.append("imdb_id = %s")
                    vals.append(imdb_coerced)

                if not sets:
                    time.sleep(args.sleep)
                    continue

                sets.append("updated_at = now()")
                q = f"UPDATE movies SET {', '.join(sets)} WHERE movie_id = %s"
                vals.append(movie_id)

                if args.dry_run:
                    print(f"- DRY {movie_id} '{title}': would update {len(sets)-1} fields")
                else:
                    cur.execute(q, tuple(vals))
                    updated += 1
                    if updated % 50 == 0:
                        conn.commit()
                        print(f"Committed {updated} updates so far")

                time.sleep(args.sleep)

        if not args.dry_run:
            conn.commit()
        print(f"Done. Checked={checked}, Updated={updated}, DryRun={args.dry_run}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()
