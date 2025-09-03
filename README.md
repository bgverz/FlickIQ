# FlickIQ - Movie Recommendation System

A production-ready hybrid movie recommendation system built with Python, LightFM, FastAPI, and Streamlit. Combines collaborative filtering with content-based filtering using the MovieLens 25M dataset and TMDB API for rich movie metadata.

## 🚀 Features

- **Hybrid Recommendations**: LightFM model combining collaborative filtering + content features (genres)
- **Real-time API**: FastAPI service with personalized recommendations, search, and trending movies
- **Rich Metadata**: TMDB integration for posters, overviews, and enhanced genre information
- **Vector Similarity**: PostgreSQL with pgvector for efficient similarity search
- **Interactive UI**: Optional Streamlit interface for easy testing and demos
- **Production Ready**: Comprehensive evaluation metrics, batched processing, and error handling

## 🏗️ Architecture

```
├── api/               # FastAPI application
├── app/              # Streamlit UI
├── config/           # Configuration and settings
├── data/             # Data loading and processing scripts
├── db/               # Database schema and migrations
├── model/            # LightFM training and evaluation
└── requirements.txt  # Python dependencies
```

## 📋 Prerequisites

- **Python 3.11** (required for LightFM compatibility)
- **PostgreSQL** with pgvector extension (Supabase recommended)
- **TMDB API** credentials (for movie metadata)
- **MovieLens 25M** dataset

## 🛠️ Quick Start

### 1. Environment Setup

```bash
# Clone the repository
git clone https://github.com/ShaunM042/FlickIQ.git
cd FlickIQ

# Create virtual environment (Python 3.11 required)
python3.11 -m venv .venv-3.11
source .venv-3.11/bin/activate  # On Windows: .venv-3.11\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the project root:

```env
# Database Configuration
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@YOUR_HOST:5432/postgres?sslmode=require

# Supabase (if using)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# TMDB API (for movie metadata)
TMDB_API_KEY=your-api-key
TMDB_ACCESS_TOKEN=your-access-token
TMDB_IMAGE_BASE=https://image.tmdb.org/t/p/w342
POSTER_PLACEHOLDER=https://placehold.co/342x513?text=No+Poster
```

### 3. Database Setup

```bash
# Enable pgvector extension in your PostgreSQL database
# Via psql or Supabase SQL Editor:
# CREATE EXTENSION IF NOT EXISTS vector;

# Set up database schema
export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:5432/postgres?sslmode=require"
python -m data.load_schema
python -m data.seed_minimal
```

### 4. Data Loading

```bash
# Download MovieLens 25M dataset
wget https://files.grouplens.org/datasets/movielens/ml-25m.zip
unzip ml-25m.zip

# Load MovieLens data (this may take 10-30 minutes)
python -m data.load_movielens \
    --movies_csv ./ml-25m/movies.csv \
    --ratings_csv ./ml-25m/ratings.csv \
    --batch_size 50000
```

### 5. TMDB Enrichment (Optional but Recommended)

```bash
# Enrich with TMDB metadata (start small for testing)
python -m data.enrich_tmdb --limit 1000 --only-missing

# For production, enrich all movies (takes several hours due to rate limits)
python -m data.enrich_tmdb --only-missing
```

### 6. Model Training

```bash
# Train the hybrid recommendation model
python -m model.train_model --epochs 10 --no_components 64 --num_threads 8

# Evaluate the model (optional)
python model/evaluate_model.py --from-db --k 10 --limit_users 1000
```

### 7. Start Services

```bash
# Terminal 1: Start FastAPI server
uvicorn api.main:app --reload --port 8000

# Terminal 2: Start Streamlit UI (optional)
export API_BASE="http://127.0.0.1:8000"
python -m streamlit run app/streamlit_app.py
```

## 🔗 API Endpoints

Once running, access the API at `http://localhost:8000`:

- **`GET /healthz`** - Health check
- **`GET /docs`** - Interactive API documentation
- **`GET /movies/search?q=batman`** - Search movies
- **`GET /recommendations/{user_id}?limit=10`** - Get personalized recommendations
- **`GET /similar/{movie_id}?limit=10`** - Get similar movies
- **`GET /trending?days=7&limit=20`** - Get trending movies
- **`POST /users`** - Create/ensure user exists
- **`POST /interactions`** - Record user-movie interactions

## 📊 Data Overview

The system processes the full MovieLens 25M dataset:
- **~62K movies** with titles, years, and genres
- **~280K users** with rating histories  
- **~25M ratings** (0.5-5.0 scale)
- **TMDB enrichment** adds posters, overviews, and enhanced metadata

## 🧪 Testing & Validation

```bash
# Check data loading status
python -m data.table_counts

# Test database connection
python test_connection.py

# View sample data
python -m data.peek_table movies
python -m data.peek_table interactions

# Comprehensive model evaluation
python model/evaluate_model.py --train --epochs 5 --no_components 64
```

## 🚀 Deployment Considerations

### Performance Tuning
- Adjust `--no_components` (embedding dimensions) based on dataset size
- Use `--limit_users` during development to work with smaller datasets
- Tune PostgreSQL `work_mem` and `shared_buffers` for large data operations

### Production Checklist
- [ ] Set up proper SSL certificates
- [ ] Configure connection pooling for PostgreSQL
- [ ] Set up monitoring and logging
- [ ] Implement rate limiting for API endpoints
- [ ] Set up automated model retraining pipeline
- [ ] Configure backup strategy for embeddings and user data

## 🛠️ Development

### Useful Commands

```bash
# Monitor data loading progress
python -m data.table_counts

# Test individual components
python -c "from config.settings import DATABASE_URL; print(DATABASE_URL)"
python -c "import psycopg2; print('Database connection OK')"

# Quick API test
curl http://localhost:8000/healthz
curl http://localhost:8000/movies/search?q=batman&limit=5
```

### Common Issues

**LightFM Installation Issues**: Use Python 3.11. Avoid Python 3.12 due to compilation issues.

**psycopg2 Build Errors**: 
```bash
pip install psycopg2-binary  # Use binary version instead of source
```

**Database Connection Issues**: Ensure pgvector extension is enabled and connection string format is correct for each tool:
- API: `postgresql+psycopg://...` (SQLAlchemy format)
- Data scripts: `postgresql://...` (standard format)

**TMDB Rate Limits**: The enrichment script automatically handles rate limiting. For faster development, work with `--limit` flag.

## 📈 Model Performance

The system uses Recall@K as the primary evaluation metric:
- **Recall@10**: Measures how many relevant items appear in top-10 recommendations
- **Cold Start Handling**: Uses item popularity fallback for new users
- **Hybrid Approach**: Combines user-item interactions with genre features

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙋‍♂️ Support

For issues and questions:
- Check the FastAPI docs at `/docs` when running locally
- Review logs for detailed error messages
- Ensure all prerequisites are installed correctly