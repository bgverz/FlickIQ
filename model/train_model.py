"""
Train a hybrid LightFM recommender on MovieLens 25M and persist embeddings.

This script:
- Loads interactions and item metadata from PostgreSQL
- Builds a LightFM Dataset with item features (genres)
- Splits data into train/test per user
- Trains a WARP model optimized for ranking
- Evaluates Recall@10 vs. a simple popularity baseline
- Saves user and item embeddings to PostgreSQL pgvector tables

Environment variables:
- DATABASE_URL: PostgreSQL connection string

Usage:
    python model/train_model.py --epochs 10 --no_components 64 --num_threads 8

Notes:
- Running on the full 25M interactions can be memory intensive. You can limit
  the number of users/interactions via CLI options for experimentation.
"""

import argparse
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from scipy import sparse
from lightfm import LightFM
from lightfm.data import Dataset
from lightfm.evaluation import recall_at_k


LOGGER = logging.getLogger("train_model")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def ensure_connection(db_url: str):
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    return conn


@dataclass
class DataSplits:
    interactions_train: sparse.coo_matrix
    interactions_test: sparse.coo_matrix
    user_id_map: Dict[int, int]
    item_id_map: Dict[int, int]
    inv_user_id_map: Dict[int, int]
    inv_item_id_map: Dict[int, int]
    item_features_matrix: Optional[sparse.csr_matrix]
    user_features_matrix: Optional[sparse.csr_matrix]


def fetch_movies_and_genres(conn, limit_items: Optional[int] = None) -> Dict[int, List[str]]:
    sql = "SELECT movie_id, genres FROM movies ORDER BY movie_id"
    if limit_items:
        sql += " LIMIT %s"
        params = (limit_items,)
    else:
        params = None
    item_to_genres: Dict[int, List[str]] = {}
    with conn.cursor() as cur:
        cur.execute(sql, params) if params else cur.execute(sql)
        for movie_id, genres in cur.fetchall():
            item_to_genres[int(movie_id)] = list(genres) if genres else []
    return item_to_genres


def fetch_interactions(conn,
                       limit_users: Optional[int] = None,
                       limit_interactions: Optional[int] = None) -> List[Tuple[int, int, float]]:
    sql = "SELECT user_id, movie_id, COALESCE(weight, rating)::float FROM interactions"
    params: Tuple = tuple()
    if limit_users is not None:
        sql += " WHERE user_id IN (SELECT user_id FROM users ORDER BY user_id LIMIT %s)"
        params += (limit_users,)
    sql += " ORDER BY user_id, movie_id"
    if limit_interactions is not None:
        sql += " LIMIT %s"
        params += (limit_interactions,)
    rows: List[Tuple[int, int, float]] = []
    with conn.cursor() as cur:
        cur.execute(sql, params if params else None)
        for uid, mid, w in cur.fetchall():
            rows.append((int(uid), int(mid), float(w if w is not None else 1.0)))
    return rows


def build_dataset(interactions: Sequence[Tuple[int, int, float]],
                  item_to_genres: Dict[int, List[str]]) -> Tuple[Dataset, Dict[int, int], Dict[int, int]]:
    user_ids = sorted({u for (u, _m, _w) in interactions})
    item_ids = sorted({m for (_u, m, _w) in interactions})

    dataset = Dataset()
    dataset.fit(users=user_ids, items=item_ids,
                item_features=set(f"genre:{g}" for genres in item_to_genres.values() for g in genres))
    user_id_map, item_id_map = dataset._user_id_mapping, dataset._item_id_mapping  # type: ignore[attr-defined]
    return dataset, user_id_map, item_id_map


def build_matrices(dataset: Dataset,
                   interactions: Sequence[Tuple[int, int, float]],
                   item_to_genres: Dict[int, List[str]]) -> Tuple[sparse.coo_matrix, Optional[sparse.csr_matrix]]:
    triples = [(u, i, w) for (u, i, w) in interactions]
    (interactions_mtx, _weights) = dataset.build_interactions(triples)

    # Build item features
    item_features_list = []
    for item_id, genres in item_to_genres.items():
        if not genres:
            continue
        tags = [f"genre:{g}" for g in genres]
        item_features_list.append((item_id, tags))
    item_features_mtx = dataset.build_item_features(((i, feats) for (i, feats) in item_features_list))
    return interactions_mtx.tocoo(), item_features_mtx.tocsr() if item_features_mtx is not None else None


def train_test_split_by_user(interactions: sparse.coo_matrix, test_fraction: float = 0.2, seed: int = 42) -> Tuple[sparse.coo_matrix, sparse.coo_matrix]:
    rng = np.random.default_rng(seed)
    interactions = interactions.tocsr()
    num_users, _ = interactions.shape
    train_rows: List[int] = []
    train_cols: List[int] = []
    test_rows: List[int] = []
    test_cols: List[int] = []
    for u in range(num_users):
        start, end = interactions.indptr[u], interactions.indptr[u + 1]
        items = interactions.indices[start:end]
        if len(items) <= 1:
            train_items = items
            test_items = []
        else:
            mask = rng.random(len(items)) < test_fraction
            test_items = items[mask]
            train_items = items[~mask]
            if len(test_items) == 0:  # ensure at least one test when possible
                test_items = items[-1:]
                train_items = items[:-1]
        train_rows.extend([u] * len(train_items))
        train_cols.extend(train_items.tolist())
        test_rows.extend([u] * len(test_items))
        test_cols.extend(test_items.tolist())
    data_train = np.ones(len(train_rows), dtype=np.float32)
    data_test = np.ones(len(test_rows), dtype=np.float32)
    train = sparse.coo_matrix((data_train, (np.array(train_rows), np.array(train_cols))), shape=interactions.shape)
    test = sparse.coo_matrix((data_test, (np.array(test_rows), np.array(test_cols))), shape=interactions.shape)
    return train, test


def compute_popularity_baseline(train: sparse.coo_matrix, test: sparse.coo_matrix, k: int = 10) -> float:
    # Popularity by global item frequency in train
    item_popularity = np.asarray(train.sum(axis=0)).ravel()
    topk_items = np.argsort(-item_popularity)[:k]
    test = test.tocsr()
    recalls: List[float] = []
    for u in range(test.shape[0]):
        test_items = set(test.indices[test.indptr[u]: test.indptr[u + 1]].tolist())
        if not test_items:
            continue
        hits = len(test_items.intersection(set(topk_items.tolist())))
        recalls.append(hits / min(k, len(test_items)))
    return float(np.mean(recalls)) if recalls else 0.0


def train_lightfm(train: sparse.coo_matrix,
                  item_features: Optional[sparse.csr_matrix],
                  no_components: int,
                  epochs: int,
                  num_threads: int) -> LightFM:
    model = LightFM(loss="warp", no_components=no_components)
    model.fit(interactions=train,
              item_features=item_features,
              epochs=epochs,
              num_threads=num_threads)
    return model


def matrix_to_vector_literal(vec: np.ndarray) -> str:
    # pgvector expects e.g. '[0.1, -0.2, ...]'
    return "[" + ",".join(f"{float(x):.6f}" for x in vec.tolist()) + "]"


def save_embeddings(conn,
                    model: LightFM,
                    dataset: Dataset,
                    user_id_map: Dict[int, int],
                    item_id_map: Dict[int, int],
                    item_features: Optional[sparse.csr_matrix]) -> None:
    # Build feature matrices to get representations
    if item_features is None:
        item_features = dataset.build_item_features([])
    user_features = dataset.build_user_features([])

    _, user_embeddings = model.get_user_representations(user_features)
    _, item_embeddings = model.get_item_representations(item_features)

    inv_user = {v: k for k, v in user_id_map.items()}
    inv_item = {v: k for k, v in item_id_map.items()}

    user_values = [
        (inv_user[row], matrix_to_vector_literal(user_embeddings[row]))
        for row in range(user_embeddings.shape[0])
        if row in inv_user
    ]
    item_values = [
        (inv_item[row], matrix_to_vector_literal(item_embeddings[row]))
        for row in range(item_embeddings.shape[0])
        if row in inv_item
    ]

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO user_embeddings (user_id, embedding)
            VALUES %s
            ON CONFLICT (user_id) DO UPDATE
            SET embedding = EXCLUDED.embedding, updated_at = now()
            """,
            user_values,
            template="(%s, %s::vector)",
            page_size=10000,
        )

        execute_values(
            cur,
            """
            INSERT INTO item_embeddings (movie_id, embedding)
            VALUES %s
            ON CONFLICT (movie_id) DO UPDATE
            SET embedding = EXCLUDED.embedding, updated_at = now()
            """,
            item_values,
            template="(%s, %s::vector)",
            page_size=10000,
        )
    conn.commit()


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Train LightFM hybrid model and save embeddings")
    parser.add_argument("--database_url", default=os.environ.get("DATABASE_URL"), help="PostgreSQL URL")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--no_components", type=int, default=64)
    parser.add_argument("--num_threads", type=int, default=8)
    parser.add_argument("--limit_users", type=int, default=None)
    parser.add_argument("--limit_interactions", type=int, default=None)
    parser.add_argument("--test_fraction", type=float, default=0.2)
    parser.add_argument("--k", type=int, default=10, help="K for Recall@K")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("--database_url or env DATABASE_URL must be provided")

    conn = ensure_connection(args.database_url)
    try:
        LOGGER.info("Fetching interactions and metadata from DB")
        interactions = fetch_interactions(conn, limit_users=args.limit_users, limit_interactions=args.limit_interactions)
        if not interactions:
            raise SystemExit("No interactions found. Load data first.")
        LOGGER.info("Loaded %d interactions", len(interactions))

        item_to_genres = fetch_movies_and_genres(conn)

        dataset, user_id_map, item_id_map = build_dataset(interactions, item_to_genres)
        interactions_mtx, item_features = build_matrices(dataset, interactions, item_to_genres)

        LOGGER.info("Performing user-wise train/test split")
        train_mtx, test_mtx = train_test_split_by_user(interactions_mtx, test_fraction=args.test_fraction)

        LOGGER.info("Training LightFM model (WARP, %d components, %d epochs)", args.no_components, args.epochs)
        model = train_lightfm(train=train_mtx, item_features=item_features, no_components=args.no_components, epochs=args.epochs, num_threads=args.num_threads)

        LOGGER.info("Evaluating Recall@%d", args.k)
        rec_lfm = recall_at_k(model, test_mtx, train_interactions=train_mtx, item_features=item_features, k=args.k, num_threads=args.num_threads).mean()
        rec_pop = compute_popularity_baseline(train_mtx, test_mtx, k=args.k)
        LOGGER.info("Recall@%d - LightFM: %.4f | Popularity: %.4f", args.k, float(rec_lfm), rec_pop)

        LOGGER.info("Saving embeddings to PostgreSQL (pgvector)")
        save_embeddings(conn, model, dataset, user_id_map, item_id_map, item_features)
        LOGGER.info("Embeddings saved successfully")
    except Exception:
        conn.rollback()
        LOGGER.exception("Training failed; rolled back last transaction")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()


