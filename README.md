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
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure env
```bash
export DATABASE_URL=postgres://user:pass@localhost:5432/movies
export TMDB_API_KEY=your_tmdb_key
```

3. Create schema (requires pgvector installed in DB)
```bash
psql "$DATABASE_URL" -f db/schema.sql
```

4. Download MovieLens 25M and load
```bash
# https://grouplens.org/datasets/movielens/25m/
python data/load_movielens.py \
  --movies_csv /path/to/ml-25m/movies.csv \
  --ratings_csv /path/to/ml-25m/ratings.csv \
  --batch_size 50000
```

5. (Optional) Enrich with TMDB
```bash
python data/enrich_tmdb.py --limit 5000 --start_offset 0
```

6. Train model and save embeddings
```bash
python model/train_model.py --epochs 10 --no_components 64 --num_threads 8
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

## Project Structure
```
.
.
├── api/
│   └── main.py              
├── app/
│   └── streamlit_app.py     
├── config/
│   └── settings.py         
│   ├── enrich_tmdb.py       
│   ├── load_movielens.py    
│   ├── load_schema.py       # Initialize schema
│   ├── seed_minimal.py      # Seed small starter dataset
│   ├── smoke_query.py       # Sanity checks
│   ├── peek_table.py        # Preview DB tables
│   └── table_counts.py      # Row counts by table
├── db/
│   └── schema.sql           
├── model/
│   ├── train_model.py       
│   └── evaluate_model.py    
├── test_connection.py       # Quick DB connection test
├── requirements.txt
├── .gitignore
└── README.md
```

## Notes
- Ensure pgvector extension is installed: `CREATE EXTENSION IF NOT EXISTS vector;`
- You can adjust embedding dimension in DB schema and the `--no_components` flag to match.
- The full 25M dataset is large; start with a subset via `--limit_users` for experimentation.

## License
MIT
