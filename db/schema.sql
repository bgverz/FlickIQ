-- PostgreSQL schema for Movie Recommendation System
-- Requires pgvector extension for vector similarity search

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;  

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id      BIGINT PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Movies table (metadata enriched later via TMDB)
CREATE TABLE IF NOT EXISTS movies (
    movie_id     BIGINT PRIMARY KEY,
    title        TEXT NOT NULL,
    year         INTEGER,
    tmdb_id      BIGINT,
    imdb_id      BIGINT,
    poster_path  TEXT,
    overview     TEXT,
    genres       TEXT[] NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Interactions table: implicit/explicit feedback
CREATE TABLE IF NOT EXISTS interactions (
    user_id          BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    movie_id         BIGINT NOT NULL REFERENCES movies(movie_id) ON DELETE CASCADE,
    rating           NUMERIC(3,1), -- 0.5 to 5.0
    interacted_at    TIMESTAMPTZ,
    interaction_type TEXT NOT NULL DEFAULT 'rating',
    weight           REAL,
    PRIMARY KEY (user_id, movie_id)
);

-- Adjust dimensions as needed to match the trained model (default 64)
CREATE TABLE IF NOT EXISTS user_embeddings (
    user_id      BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    embedding    VECTOR(64) NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS item_embeddings (
    movie_id     BIGINT PRIMARY KEY REFERENCES movies(movie_id) ON DELETE CASCADE,
    embedding    VECTOR(64) NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Useful indexes
CREATE INDEX IF NOT EXISTS interactions_user_idx ON interactions(user_id);
CREATE INDEX IF NOT EXISTS interactions_movie_idx ON interactions(movie_id);
CREATE INDEX IF NOT EXISTS movies_genres_gin ON movies USING GIN (genres);

-- Vector indexes (requires pgvector ≥ 0.4.0)
CREATE INDEX IF NOT EXISTS item_embeddings_vec_l2 ON item_embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS user_embeddings_vec_l2 ON user_embeddings USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- CREATE MATERIALIZED VIEW IF NOT EXISTS mv_movie_popularity AS
-- SELECT movie_id,
--        COUNT(*) AS interactions_count,
--        AVG(rating) AS avg_rating
-- FROM interactions
-- GROUP BY movie_id;


