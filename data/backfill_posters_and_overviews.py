# data/backfill_posters_and_overviews.py
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
    
    # Find movies with TMDB IDs but missing poster OR overview
    cur.execute("""
      SELECT movie_id, tmdb_id FROM movies
      WHERE tmdb_id IS NOT NULL 
        AND (poster_path IS NULL OR poster_path = '' OR overview IS NULL OR overview = '')
      LIMIT 500
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} movies to backfill")
    
    updated_count = 0
    for mid, tid in rows:
        try:
            data = tmdb_movie(tid)
            poster = data.get("poster_path")
            overview = data.get("overview", "")
            
            # Update both poster and overview if we got data
            updates = []
            params = []
            
            if poster:
                updates.append("poster_path = %s")
                params.append(poster)
            
            if overview:
                updates.append("overview = %s")
                params.append(overview)
            
            if updates:
                updates.append("updated_at = now()")
                params.append(mid)
                
                query = f"UPDATE movies SET {', '.join(updates)} WHERE movie_id = %s"
                cur.execute(query, params)
                
                print(f"Updated movie {mid}: poster={bool(poster)}, overview={bool(overview)}")
                updated_count += 1
            
            time.sleep(0.25)  # be nice to TMDB
            
        except Exception as e:
            print(f"Failed {mid}/{tid}: {e}")
    
    print(f"\nSUCCESS: Updated {updated_count} movies with TMDB data!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
