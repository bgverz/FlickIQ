# data/enrich_by_title.py
import os, time, requests, psycopg2
import re

TMDB_KEY = os.environ["TMDB_API_KEY"]
DB_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

def clean_title(title):
    """Clean movie title for better TMDB matching"""
    # Remove year from title
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    # Handle "Title, The" format
    if title.endswith(', The'):
        title = 'The ' + title[:-5]
    elif title.endswith(', A'):
        title = 'A ' + title[:-3]
    return title.strip()

def search_tmdb_movie(title, year):
    """Search TMDB by title and year"""
    url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_KEY,
        "query": title,
        "year": year
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    
    # Return the first result if any
    if data.get('results'):
        return data['results'][0]
    return None

def get_tmdb_movie_details(tmdb_id):
    """Get full movie details from TMDB"""
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    r = requests.get(url, params={"api_key": TMDB_KEY})
    r.raise_for_status()
    return r.json()

def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Get popular movies without TMDB data
    cur.execute("""
        SELECT movie_id, title, year 
        FROM movies
        WHERE tmdb_id IS NULL 
          AND (poster_path IS NULL OR poster_path = '')
          AND title IS NOT NULL
          AND year IS NOT NULL
        ORDER BY movie_id  -- Start with early movie IDs (often more popular)
        LIMIT 50
    """)
    
    rows = cur.fetchall()
    print(f"Found {len(rows)} movies to search and enrich")
    
    updated_count = 0
    for movie_id, title, year in rows:
        try:
            # Clean the title for better matching
            clean_title_text = clean_title(title)
            print(f"Searching for: '{clean_title_text}' ({year})")
            
            # Search TMDB
            search_result = search_tmdb_movie(clean_title_text, year)
            if not search_result:
                print(f"  No TMDB match found for {title}")
                continue
            
            tmdb_id = search_result['id']
            
            # Get full details
            movie_details = get_tmdb_movie_details(tmdb_id)
            
            poster_path = movie_details.get('poster_path')
            overview = movie_details.get('overview', '')
            
            # Update the movie
            cur.execute("""
                UPDATE movies 
                SET tmdb_id = %s, 
                    poster_path = %s, 
                    overview = %s,
                    updated_at = now()
                WHERE movie_id = %s
            """, (tmdb_id, poster_path, overview, movie_id))
            
            print(f"  ✅ Updated {title}: TMDB ID {tmdb_id}, poster={bool(poster_path)}")
            updated_count += 1
            
            time.sleep(0.3)  # Be nice to TMDB API
            
        except Exception as e:
            print(f"  ❌ Failed {title}: {e}")
    
    print(f"\n🎉 SUCCESS: Updated {updated_count} movies!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
