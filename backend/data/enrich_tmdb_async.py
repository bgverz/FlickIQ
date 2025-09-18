from __future__ import annotations
"""
Async bulk TMDB enrichment:
- Parallel, rate-limited TMDB calls (fast)
- Prefers tmdb_id, then imdb_id (/find), then cleaned title search
- Fills poster_path, overview, year, genres, tmdb_id, imdb_id (only when missing)
- Bulk-updates in batches for speed

Usage:
  set -a; source .env; set +a
  python -m data.enrich_tmdb_async --limit 200000 --only-missing --qps 6 --concurrency 20
"""

import argparse
import asyncio
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

import aiohttp
from aiolimiter import AsyncLimiter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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

# ---------------- Title normalization ----------------
def strip_year_suffix(title: str) -> str:
    return re.sub(r"\s*\(\d{4}\)\s*$", "", title or "").strip()

def remove_parentheticals(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", title or "").strip()

def untail_article(title: str) -> str:
    m = re.match(r"^(.*),\s*(A|An|The)$", (title or "").strip(), flags=re.IGNORECASE)
    if not m:
        return (title or "").strip()
    core, art = m.group(1).strip(), m.group(2).strip()
    return f"{art} {core}"

def normalize_title(title: str) -> str:
    t = strip_year_suffix(title)
    t = remove_parentheticals(t)
    t = untail_article(t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t

# ---------------- IMDb column type & coercion ----------------
def get_imdb_column_type(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='movies' AND column_name='imdb_id'
        """)
        row = cur.fetchone()
    return (row[0].lower() if row and row[0] else "text")

def coerce_imdb_value(raw: Any, target_type: str) -> Optional[Any]:
    if raw is None:
        return None
    if target_type in ("bigint","integer","numeric","decimal","smallint"):
        if isinstance(raw, str) and raw.startswith("tt"):
            num = raw[2:]
            return int(num) if num.isdigit() else None
        try:
            return int(str(raw))
        except Exception:
            return None
    return str(raw)

# ---------------- TMDB client (async) ----------------
class TMDB:
    def __init__(self, session: aiohttp.ClientSession, limiter: AsyncLimiter):
        self.sess = session
        self.limiter = limiter

    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _get(self, path: str, **params) -> Dict[str, Any]:
        params = {"api_key": TMDB_KEY, "include_adult": "false", "language": "en-US", **params}
        async with self.limiter:
            async with self.sess.get(f"{BASE}{path}", params=params, timeout=20) as r:
                if r.status == 429:
                    # Let tenacity backoff/retry
                    raise aiohttp.ClientError("429 Too Many Requests")
                r.raise_for_status()
                return await r.json()

    async def movie_details(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self._get(f"/movie/{tmdb_id}")
        except Exception:
            return None

    async def find_by_imdb(self, imdb_id: str) -> Optional[int]:
        try:
            data = await self._get(f"/find/{imdb_id}", external_source="imdb_id")
            movies = data.get("movie_results") or []
            return int(movies[0]["id"]) if movies else None
        except Exception:
            return None

    async def search_best(self, title: str, year: Optional[int]) -> Optional[int]:
        candidates: List[Tuple[str, Optional[int]]] = []
        base = normalize_title(title or "")
        candidates.append((base, year))
        candidates.append((base, None))
        if re.search(r",\s*(A|An|The)$", base, flags=re.IGNORECASE):
            swapped = untail_article(base)
            if swapped != base:
                candidates.append((swapped, year))
                candidates.append((swapped, None))
        seen = set()
        for t, y in candidates:
            key = (t.lower(), y)
            if key in seen:
                continue
            seen.add(key)
            try:
                params = {"query": t}
                if y:
                    params["year"] = int(y)
                data = await self._get("/search/movie", **params)
                res = data.get("results") or []
                if res:
                    return int(res[0]["id"])
            except Exception:
                continue
        return None

def extract_fields(j: Dict[str, Any]) -> Dict[str, Any]:
    if not j:
        return {}
    release_date = j.get("release_date") or ""
    year = int(release_date[:4]) if release_date[:4].isdigit() else None
    genres = [g.get("name") for g in (j.get("genres") or []) if g.get("name")]
    return {
        "tmdb_id": j.get("id"),
        "imdb_id": j.get("imdb_id"),
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

# ---------------- Worker ----------------
async def worker(row: Tuple[Any, ...], tmdb: TMDB, imdb_type: str, overwrite_flags: Dict[str, bool]) -> Optional[Tuple[int, Dict[str, Any]]]:
    movie_id, title, year, tmdb_id, imdb_id, poster_path, overview, genres = row

    details = None
    if tmdb_id:
        details = await tmdb.movie_details(int(tmdb_id))
    if details is None and imdb_id:
        # imdb_id could be numeric or 'tt...'
        imdb_str = f"tt{int(imdb_id)}" if isinstance(imdb_id, (int,)) else str(imdb_id)
        tmdb_found = await tmdb.find_by_imdb(imdb_str)
        if tmdb_found:
            details = await tmdb.movie_details(tmdb_found)
    if details is None:
        tmdb_found = await tmdb.search_best(title or "", int(year) if year else None)
        if tmdb_found:
            details = await tmdb.movie_details(tmdb_found)

    if not details:
        return None

    fields = extract_fields(details)
    updates: Dict[str, Any] = {}

    if should_update(poster_path, fields.get("poster_path"), overwrite_flags["posters"]):
        updates["poster_path"] = fields.get("poster_path")

    if should_update(overview, fields.get("overview"), overwrite_flags["overview"]):
        updates["overview"] = fields.get("overview")

    if should_update(year, fields.get("year"), overwrite_flags["year"]):
        updates["year"] = fields.get("year")

    if should_update(genres, fields.get("genres"), overwrite_flags["genres"]):
        updates["genres"] = fields.get("genres")

    if should_update(tmdb_id, fields.get("tmdb_id"), False):
        updates["tmdb_id"] = fields.get("tmdb_id")

    imdb_raw = fields.get("imdb_id")
    imdb_coerced = coerce_imdb_value(imdb_raw, imdb_type)
    if should_update(imdb_id, imdb_coerced, False):
        updates["imdb_id"] = imdb_coerced

    return (int(movie_id), updates) if updates else None

# ---------------- Main ----------------
def fetch_rows(conn, limit: int, only_missing: bool) -> List[Tuple[Any, ...]]:
    where = ""
    if only_missing:
        where = "WHERE (poster_path IS NULL OR poster_path='' OR overview IS NULL OR overview='')"
    sql = f"""
        SELECT movie_id, title, year, tmdb_id, imdb_id, poster_path, overview, genres
        FROM movies
        {where}
        ORDER BY movie_id
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        return cur.fetchall()

def bulk_update(conn, batch: List[Tuple[int, Dict[str, Any]]]) -> int:
    if not batch:
        return 0
    cols = ["poster_path", "overview", "year", "genres", "tmdb_id", "imdb_id"]
    rows = []
    for mid, upd in batch:
        rows.append((
            mid,
            upd.get("poster_path"),
            upd.get("overview"),
            upd.get("year"),
            upd.get("genres"),
            upd.get("tmdb_id"),
            upd.get("imdb_id"),
        ))
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE tmp_updates (
                movie_id BIGINT PRIMARY KEY,
                poster_path TEXT,
                overview TEXT,
                year INTEGER,
                genres TEXT[],
                tmdb_id BIGINT,
                imdb_id TEXT
            ) ON COMMIT DROP
        """)
        execute_values(cur,
            "INSERT INTO tmp_updates (movie_id, poster_path, overview, year, genres, tmdb_id, imdb_id) VALUES %s",
            rows,
            page_size=1000
        )
        cur.execute("""
            UPDATE movies m
            SET
              poster_path = COALESCE(t.poster_path, m.poster_path),
              overview    = COALESCE(t.overview,    m.overview),
              year        = COALESCE(t.year,        m.year),
              genres      = COALESCE(t.genres,      m.genres),
              tmdb_id     = COALESCE(t.tmdb_id,     m.tmdb_id),
              imdb_id     = COALESCE(t.imdb_id::text, m.imdb_id::text)::text
            FROM tmp_updates t
            WHERE m.movie_id = t.movie_id
        """)
    conn.commit()
    return len(batch)

async def main_async(args):
    # DB setup
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    imdb_type = get_imdb_column_type(conn)
    print(f"Detected movies.imdb_id type: {imdb_type}")

    rows = fetch_rows(conn, args.limit, args.only_missing)
    total = len(rows)
    print(f"Fetched {total} rows to process")

    # HTTP client & rate limit
    limiter = AsyncLimiter(max_rate=args.qps, time_period=1)
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(limit=args.concurrency)

    overwrite_flags = {
        "posters": args.overwrite_posters,
        "overview": args.overwrite_overview,
        "year": args.overwrite_year,
        "genres": args.overwrite_genres,
    }

    processed = 0
    updated_rows: List[Tuple[int, Dict[str, Any]]] = []
    batch_flush = args.batch_size

    start = time.time()
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tmdb = TMDB(session, limiter)

        sem = asyncio.Semaphore(args.concurrency)
        async def bound_worker(r):
            async with sem:
                return await worker(r, tmdb, imdb_type, overwrite_flags)

        for chunk_start in range(0, total, args.concurrency * 10):
            chunk = rows[chunk_start:chunk_start + args.concurrency * 10]
            results = await asyncio.gather(*(bound_worker(r) for r in chunk), return_exceptions=True)
            for res in results:
                processed += 1
                if isinstance(res, tuple):
                    updated_rows.append(res)
                if len(updated_rows) >= batch_flush:
                    n = bulk_update(conn, updated_rows)
                    updated_rows.clear()
                    elapsed = time.time() - start
                    print(f"Processed {processed}/{total} | Applied {n} updates | {elapsed:.1f}s")

        if updated_rows:
            n = bulk_update(conn, updated_rows)
            print(f"Final apply: {n} updates")
    conn.close()
    elapsed = time.time() - start
    print(f"Done in {elapsed:.1f}s (processed {processed}, limit {total})")

def main():
    ap = argparse.ArgumentParser(description="Async enrich movies from TMDB")
    ap.add_argument("--limit", type=int, default=50000)
    ap.add_argument("--only-missing", action="store_true")
    ap.add_argument("--overwrite-posters", action="store_true")
    ap.add_argument("--overwrite-overview", action="store_true")
    ap.add_argument("--overwrite-year", action="store_true")
    ap.add_argument("--overwrite-genres", action="store_true")
    ap.add_argument("--qps", type=float, default=6.0, help="Requests per second to TMDB")
    ap.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    ap.add_argument("--batch-size", type=int, default=500, help="DB update batch size")
    args = ap.parse_args()
    asyncio.run(main_async(args))

if __name__ == "__main__":
    main()
