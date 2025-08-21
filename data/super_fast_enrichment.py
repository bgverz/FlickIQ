# data/super_fast_enrichment.py
import os, time, requests, psycopg2
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

TMDB_KEY = os.environ["TMDB_API_KEY"]
DB_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

# Thread-safe counter
class Counter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
            return self._value

def get_tmdb_data(tmdb_id):
    """Fetch movie data from TMDB API"""
    try:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
        r = requests.get(url, params={"api_key": TMDB_KEY}, timeout=15)
        if r.status_code == 404:
            return tmdb_id, None, None, False  # Movie not found
        r.raise_for_status()
        data = r.json()
        return tmdb_id, data.get("poster_path"), data.get("overview", ""), True
    except Exception as e:
        return tmdb_id, None, None, False

def bulk_update_movies(updates):
    """Bulk update movies in database"""
    if not updates:
        return 0
    
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    updated_count = 0
    for movie_id, poster, overview in updates:
        try:
            update_parts = []
            params = []
            
            if poster:
                update_parts.append("poster_path = %s")
                params.append(poster)
            
            if overview:
                update_parts.append("overview = %s")
                params.append(overview)
            
            if update_parts:
                update_parts.append("updated_at = now()")
                params.append(movie_id)
                
                query = f"UPDATE movies SET {', '.join(update_parts)} WHERE movie_id = %s"
                cur.execute(query, params)
                updated_count += 1
                
        except Exception as e:
            print(f"Failed to update movie {movie_id}: {e}")
    
    cur.close()
    conn.close()
    return updated_count

def main():
    print("🚀 SUPER FAST Movie Enrichment - Large Scale!")
    
    # Get a large batch of movies needing enrichment
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT movie_id, tmdb_id FROM movies
        WHERE tmdb_id IS NOT NULL 
          AND (poster_path IS NULL OR poster_path = '' OR overview IS NULL OR overview = '')
        LIMIT 10000
    """)
    rows = cur.fetchall()
    total_movies = len(rows)
    
    print(f"📊 Processing {total_movies} movies with 25 parallel threads...")
    print("⚡ This should complete in 10-15 minutes!")
    
    cur.close()
    conn.close()
    
    # Process with high parallelism
    updates_batch = []
    counter = Counter()
    failed_count = 0
    
    with ThreadPoolExecutor(max_workers=25) as executor:
        # Create movie_id -> tmdb_id mapping
        id_mapping = {tmdb_id: movie_id for movie_id, tmdb_id in rows}
        
        # Submit all jobs
        futures = {executor.submit(get_tmdb_data, tmdb_id): tmdb_id for _, tmdb_id in rows}
        
        for future in as_completed(futures):
            tmdb_id = futures[future]
            movie_id = id_mapping[tmdb_id]
            
            try:
                returned_tmdb_id, poster, overview, success = future.result()
                
                if success and (poster or overview):
                    updates_batch.append((movie_id, poster, overview))
                elif not success:
                    failed_count += 1
                
                # Bulk update every 200 movies
                if len(updates_batch) >= 200:
                    updated = bulk_update_movies(updates_batch)
                    total_updated = counter._value + updated
                    counter._value = total_updated
                    print(f"✅ Updated {total_updated} movies so far... ({failed_count} failed)")
                    updates_batch = []
                    
            except Exception as e:
                failed_count += 1
    
    # Update remaining movies
    if updates_batch:
        updated = bulk_update_movies(updates_batch)
        counter._value += updated
    
    print(f"\n🎉 MEGA SUCCESS!")
    print(f"✅ Total updated: {counter._value} movies")
    print(f"❌ Failed: {failed_count} movies")
    print(f"📈 Your database now has thousands more enriched movies!")
    print(f"\n🎬 Go test your Streamlit app - it should look amazing now!")

if __name__ == "__main__":
    main()
