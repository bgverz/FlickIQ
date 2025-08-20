-- Switch item/user embedding indexes to cosine ops
DROP INDEX IF EXISTS item_embeddings_vec_l2;
DROP INDEX IF EXISTS user_embeddings_vec_l2;

CREATE INDEX IF NOT EXISTS item_embeddings_vec_cos
  ON item_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX IF NOT EXISTS user_embeddings_vec_cos
  ON user_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
