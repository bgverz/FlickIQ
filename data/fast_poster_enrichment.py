import os, time, requests, psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed

TMDB_KEY = os.environ["TMDB_API_KEY"]
DB_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

def get_tmdb_data(tmdb_id):
    try:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
        r = requests.get(url, params={"api_key": TMDB_KEY}, timeout=10)
        r.raise_for_status()
        data = r.json()
        return tmdb_id, data.get("poster_path"), data.get("overview", "")
    except:
        return tmdb_id, None, None

def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Get movies missing data - larger batch
    cur.execute("""
        SELECT movie_id, tmdb_id FROM movies
        WHERE tmdb_id IS NOT NULL 
          AND (poster_path IS NULL OR poster_path = '' OR overview IS NULL OR overview = '')
        LIMIT 2000
    """)
    rows = cur.fetchall()
    print(f"Processing {len(rows)} movies with 10 parallel threads...")
    
    # Process in parallel with 10 threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_tmdb_data, tmdb_id): (movie_id, tmdb_id) 
                  for movie_id, tmdb_id in rows}
        
        updated = 0
        for future in as_completed(futures):
            movie_id, original_tmdb_id = futures[future]
            tmdb_id, poster, overview = future.result()
            
            if poster or overview:
                updates = []
                params = []
                
                if poster:
                    updates.append("poster_path = %s")
                    params.append(poster)
                
                if overview:
                    updates.append("overview = %s")
                    params.append(overview)
                
                if updates:
                    params.append(movie_id)
                    query = f"UPDATE movies SET {', '.join(updates)}, updated_at = now() WHERE movie_id = %s"
                    cur.execute(query, params)
                    updated += 1
                    
                    if updated % 100 == 0:
                        print(f"Updated {updated} movies...")
    
    print(f"SUCCESS: Updated {updated} movies!")

if __name__ == "__main__":
    main()
