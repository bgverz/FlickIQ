# data/backfill_user_embeddings.py
from __future__ import annotations
import os
import re
import psycopg2
import numpy as np

def _normalize_dsn(raw: str | None) -> str:
    if not raw:
        raise RuntimeError("DATABASE_URL is not set")
    # psycopg2 expects postgresql://..., not postgresql+psycopg://...
    return raw.replace("postgresql+psycopg://", "postgresql://")

def _vec_to_array(s: str) -> np.ndarray:
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    return np.array([float(x) for x in nums], dtype=np.float32)

def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        # fall back to project config (loads .env)
        from config.settings import DATABASE_URL as CFG
        dsn = CFG
    dsn = _normalize_dsn(dsn)

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT user_id
            FROM public.interactions
            ORDER BY user_id
        """)
        users = [r[0] for r in cur.fetchall()]

        upserts = 0
        for uid in users:
            cur.execute("""
                SELECT ie.embedding
                FROM public.interactions i
                JOIN public.item_embeddings ie ON ie.movie_id = i.movie_id
                WHERE i.user_id = %s
            """, (uid,))
            rows = cur.fetchall()
            if not rows:
                continue

            mats = np.vstack([_vec_to_array(r[0]) for r in rows])
            mean_vec = mats.mean(axis=0)
            vec_str = "[" + ", ".join(f"{x:.6f}" for x in mean_vec) + "]"

            cur.execute("""
                INSERT INTO public.user_embeddings (user_id, embedding, updated_at)
                VALUES (%s, %s::vector, NOW())
                ON CONFLICT (user_id) DO UPDATE
                  SET embedding = EXCLUDED.embedding, updated_at = NOW()
            """, (uid, vec_str))
            upserts += 1

        print(f"Upserted embeddings for {upserts} users.")

if __name__ == "__main__":
    main()
