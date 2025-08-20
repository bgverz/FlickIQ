# Movie Recommendation System (LightFM + pgvector)

A modular, production-style hybrid movie recommender built on MovieLens 25M using LightFM, PostgreSQL, pgvector, FastAPI, and optional Streamlit UI.

## Features
- Hybrid LightFM model (collaborative + genres as content features)
- PostgreSQL schema with pgvector to store embeddings
- TMDB enrichment for posters, overview, genres
- FastAPI service for `/recommendations/{user_id}` and `/trending`
- Evaluation scripts and metrics (Recall@10)

## Setup
1. Clone and install deps
```bash
python3.11 -m venv .venv-3.11
source .venv-3.11/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2. Configure env
```bash
SUPABASE_URL=<URL>
SUPABASE_ANON_KEY=<KEY>


# Preferred single connection string (psycopg3)
DATABASE_URL=postgresql+psycopg://postgres:<PASSWORD>@db.pzywmzybolnmtqenwydj.supabase.co:5432/postgres?sslmode=require


# (Optional fallback pieces — used only if DATABASE_URL is missing)
DB_HOST=db.pzywmzybolnmtqenwydj.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=<PASSWORD>
DB_SSLMODE=require

# --- TMDB (posters & metadata) ---
TMDB_API_KEY=<KEY>
TMDB_ACCESS_TOKEN=<TOKEN>
TMDB_IMAGE_BASE=https://image.tmdb.org/t/p/w342
POSTER_PLACEHOLDER=https://placehold.co/342x513?text=No+Poster

```

3. Create schema (requires pgvector installed in DB)
```bash
DB_URL="${DATABASE_URL/postgresql+psycopg:\/\//postgresql://}"
psql "$DB_URL" -f db/schema.sql
```

4. Download MovieLens 25M and load
```bash
python -m data.load_schema
python -m data.seed_minimal
python -m data.load_movielens \
  --movies_csv /path/to/ml-25m/movies.csv \
  --ratings_csv /path/to/ml-25m/ratings.csv \
  --batch_size 50000
```

5. (Optional) Enrich with TMDB
```bash
python -m data.enrich_tmdb --limit 100000 --only-missing
```

6. Train model and save embeddings
```bash
python -m model.train_model --epochs 10 --no_components 64 --num_threads 8
```

7. Evaluate
```bash
python model/evaluate_model.py --train --epochs 5 --no_components 64
python model/evaluate_model.py --from-db --k 10 --limit_users 10000
```

8. Run API
```bash
uvicorn api.main:app --reload --port 8000
# GET http://localhost:8000/recommendations/123?limit=10
# GET http://localhost:8000/trending?days=7&limit=20
```

9. Run Streamlit UI
```bash
python -m pip install streamlit requests

#IN SECOND TERMINAL
export API_BASE="http://127.0.0.1:8000"
python -m streamlit run app/streamlit_app.py
```

## Project Structure
```
├── api/
│   └── main.py                 
├── app/
│   └── streamlit_app.py        
├── config/
│   └── settings.py             
│   ├── enrich_tmdb.py          
│   ├── enrich_tmdb_async.py    
│   ├── load_movielens.py       
│   ├── load_schema.py          
│   ├── seed_minimal.py         
│   ├── smoke_query.py          
│   ├── peek_table.py           
│   └── table_counts.py         
├── db/
│   └── schema.sql              
├── model/
│   ├── train_model.py          
│   └── evaluate_model.py       
├── test_connection.py          
├── requirements.txt
├── .gitignore
└── README.md
```

## Notes
- Ensure pgvector extension is installed: `CREATE EXTENSION IF NOT EXISTS vector;`
- You can adjust embedding dimension in DB schema and the `--no_components` flag to match.
- The full 25M dataset is large; start with a subset via `--limit_users` for experimentation.
- LightFM has had issues running in a venv using Python 3.12. If timeout issues are encountered, switch to version 3.11

## License
MIT
