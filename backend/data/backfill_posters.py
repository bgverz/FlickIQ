# data/backfill_posters.py
import os, time, requests, psycopg2

TMDB_KEY = os.environ["TMDB_API_KEY"]
DB_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

def tmdb_movie(tmdb_id):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    r = requests.get(url, params={"api_key": TMDB_KEY})
    r.raise_for_status()
    return r.json()

def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
      SELECT movie_id, tmdb_id FROM movies
      WHERE poster_path IS NULL AND tmdb_id IS NOT NULL
      LIMIT 500
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} movies to backfill")
    for mid, tid in rows:
        try:
            data = tmdb_movie(tid)
            poster = data.get("poster_path")
            if poster:
                cur.execute("UPDATE movies SET poster_path=%s, updated_at=now() WHERE movie_id=%s", (poster, mid))
                print(f"Updated {mid} -> {poster}")
            time.sleep(0.2)  # be nice to TMDB
        except Exception as e:
            print(f"Failed {mid}/{tid}: {e}")
    cur.close(); conn.close()

if __name__ == "__main__":
    main()
