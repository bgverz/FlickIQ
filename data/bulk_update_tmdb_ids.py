# data/bulk_update_tmdb_ids.py
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DB_URL = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")

def main():
    print("🎬 Bulk updating TMDB IDs from MovieLens dataset...")
    
    # Read the links file
    print("📖 Reading ml-32m/links.csv...")
    links_df = pd.read_csv('ml-32m/links.csv')
    print(f"Found {len(links_df)} movie links in dataset")
    
    # Filter out rows without TMDB IDs
    valid_links = links_df.dropna(subset=['tmdbId'])
    print(f"Found {len(valid_links)} movies with TMDB IDs")
    
    # Connect to database
    print("🔗 Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Check how many movies we have in database
    cur.execute("SELECT COUNT(*) FROM movies")
    total_movies = cur.fetchone()[0]
    print(f"Database has {total_movies} movies")
    
    # Prepare data for bulk update
    update_data = [(int(row['tmdbId']), int(row['movieId'])) for _, row in valid_links.iterrows()]
    
    print(f"🚀 Bulk updating {len(update_data)} TMDB IDs...")
    
    # Bulk update using execute_values (much faster than individual updates)
    execute_values(
        cur,
        """
        UPDATE movies 
        SET tmdb_id = data.tmdb_id, updated_at = now()
        FROM (VALUES %s) AS data(tmdb_id, movie_id)
        WHERE movies.movie_id = data.movie_id
        """,
        update_data,
        template=None,
        page_size=1000
    )
    
    # Check results
    cur.execute("SELECT COUNT(*) FROM movies WHERE tmdb_id IS NOT NULL")
    updated_count = cur.fetchone()[0]
    
    print(f"✅ SUCCESS! Updated {updated_count} movies with TMDB IDs")
    print(f"📈 Increased from ~1,066 to {updated_count} movies with TMDB IDs")
    
    cur.close()
    conn.close()
    
    print("\n🎯 Next step: Run the poster enrichment script!")
    print("   python data/backfill_posters_and_overviews.py")

if __name__ == "__main__":
    main()
