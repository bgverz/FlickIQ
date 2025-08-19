"""
Train a hybrid LightFM recommender on MovieLens and persist embeddings.

Changes vs previous version:
- Auto-normalizes SQLAlchemy-style URLs (postgresql+psycopg://...) to psycopg2 (postgresql://)
- Filters item feature building to ONLY items present in the interactions matrix
  to avoid "ValueError: item id X not in item id mappings" from LightFM.

Usage:
    python -m model.train_model --database_url ... --epochs 10 --no_components 64 --num_threads 8
"""

from __future__ import annotations

import argparse
import logging
import os
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


# ----------------------------
# Utilities / IO
# ----------------------------

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def normalize_db_url(url: str) -> str:
    """
    Convert SQLAlchemy-style driver URL to a libpq/psycopg2-friendly DSN.
    e.g., postgresql+psycopg:// -> postgresql://
    """
    if not url:
        return url
    return url.replace("postgresql+psycopg://", "postgresql://")


def ensure_connection(db_url: str):
    dsn = normalize_db_url(db_url)
    conn = psycopg2.connect(dsn)
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
    """
    Returns {movie_id: [genre, ...]}.
    Assumes 'movies(genres)' is an array/text[]; adjust casting if needed.
    """
    sql = "SELECT movie_id, genres FROM movies ORDER BY movie_id"
    params = None
    if limit_items:
        sql += " LIMIT %s"
        params = (limit_items,)
    item_to_genres: Dict[int, List[str]] = {}
    with conn.cursor() as cur:
        cur.execute(sql, params) if params else cur.execute(sql)
        for movie_id, genres in cur.fetchall():
            # genres may be None or a list-like; coerce safely
            item_to_genres[int(movie_id)] = list(genres) if genres else []
    return item_to_genres


def fetch_interactions(
    conn,
    limit_users: Optional[int] = None,
    limit_interactions: Optional[int] = None,
) -> List[Tuple[int, int, float]]:
    """
    Returns list of (user_id, movie_id, weight).
    Uses COALESCE(weight, rating) if both exist.
    """
    sql = "SELECT user_id, movie_id, COALESCE(weight, rating)::float FROM interactions"
    params: List[object] = []
    if limit_users is not None:
        sql += " WHERE user_id IN (SELECT user_id FROM users ORDER BY user_id LIMIT %s)"
        params.append(limit_users)
    sql += " ORDER BY user_id, movie_id"
    if limit_interactions is not None:
        sql += " LIMIT %s"
        params.append(limit_interactions)

    rows: List[Tuple[int, int, float]] = []
    with conn.cursor() as cur:
        cur.execute(sql, tuple(params) if params else None)
        for uid, mid, w in cur.fetchall():
            rows.append((int(uid), int(mid), float(w if w is not None else 1.0)))
    return rows


# ----------------------------
# Matrix building / modeling
# ----------------------------

def build_dataset(
    interactions: Sequence[Tuple[int, int, float]],
    item_to_genres: Dict[int, List[str]],
) -> Tuple[Dataset, Dict[int, int], Dict[int, int]]:
    user_ids = sorted({u for (u, _m, _w) in interactions})
    # IMPORTANT: items limited to those that appear in interactions
    item_ids = sorted({m for (_u, m, _w) in interactions})

    # Features set built from whatever genres exist (can be superset)
    feature_tokens = {f"genre:{g}" for genres in item_to_genres.values() for g in (genres or [])}

    dataset = Dataset()
    dataset.fit(users=user_ids, items=item_ids, item_features=feature_tokens)
    user_id_map = dataset._user_id_mapping.copy()
    item_id_map = dataset._item_id_mapping.copy()
    return dataset, user_id_map, item_id_map


def build_matrices(
    dataset: Dataset,
    interactions: Sequence[Tuple[int, int, float]],
    item_to_genres: Dict[int, List[str]],
) -> Tuple[sparse.coo_matrix, Optional[sparse.csr_matrix]]:
    """
    Build interaction matrix and item feature matrix.

    CRITICAL FIX:
    Only build item features for items that were passed to dataset.fit (i.e., those
    that actually appear in interactions). This avoids LightFM mapping errors.
    """
    # Interactions
    (interactions_mtx, _weights) = dataset.build_interactions(
        ((u, i, w) for (u, i, w) in interactions)
    )

    # Restrict features to items known to the dataset (appear in interactions)
    known_items = set(dataset._item_id_mapping.keys())
    # Build (item_id, ["genre:..."]) pairs only for known items
    def _iter_item_feats() -> Iterable[Tuple[int, List[str]]]:
        for item_id, genres in item_to_genres.items():
            if item_id not in known_items:
                continue
            if not genres:
                continue
            yield (item_id, [f"genre:{g}" for g in genres])

    # If there are no features, return None; LightFM can still train
    it = list(_iter_item_feats())
    item_features_mtx = (
        dataset.build_item_features(((i, feats) for (i, feats) in it))
        if it
        else None
    )

    return interactions_mtx.tocoo(), (item_features_mtx.tocsr() if item_features_mtx is not None else None)


def train_test_split_by_user(
    interactions: sparse.coo_matrix, test_fraction: float = 0.2, seed: int = 42
) -> Tuple[sparse.coo_matrix, sparse.coo_matrix]:
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
            if len(test_items) == 0:
                test_items = items[-1:]
                train_items = items[:-1]

        train_rows.extend([u] * len(train_items))
        train_cols.extend(train_items.tolist())
        test_rows.extend([u] * len(test_items))
        test_cols.extend(test_items.tolist())

    data_train = np.ones(len(train_rows), dtype=np.float32)
    data_test = np.ones(len(test_rows), dtype=np.float32)
    shape = interactions.shape
    train = sparse.coo_matrix((data_train, (np.array(train_rows), np.array(train_cols))), shape=shape)
    test = sparse.coo_matrix((data_test, (np.array(test_rows), np.array(test_cols))), shape=shape)
    return train, test


def compute_popularity_baseline(train: sparse.coo_matrix, test: sparse.coo_matrix, k: int = 10) -> float:
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


def train_lightfm(
    train: sparse.coo_matrix,
    item_features: Optional[sparse.csr_matrix],
    no_components: int,
    epochs: int,
    num_threads: int,
) -> LightFM:
    model = LightFM(loss="warp", no_components=no_components)
    model.fit(
        interactions=train,
        item_features=item_features,
        epochs=epochs,
        num_threads=num_threads,
    )
    return model


# ----------------------------
# Persist embeddings (pgvector)
# ----------------------------

def _matrix_to_vector_literal(vec: np.ndarray) -> str:
    # emits a JSON-ish literal; the SQL casts to ::vector
    return "[" + ",".join(f"{float(x):.6f}" for x in vec.tolist()) + "]"


def save_embeddings(
    conn,
    model: LightFM,
    dataset: Dataset,
    user_id_map: Dict[int, int],
    item_id_map: Dict[int, int],
    item_features: Optional[sparse.csr_matrix],
) -> None:
    # Ensure feature matrices exist for representation extraction
    if item_features is None:
        item_features = dataset.build_item_features([])
    user_features = dataset.build_user_features([])

    _, user_embeddings = model.get_user_representations(user_features)
    _, item_embeddings = model.get_item_representations(item_features)

    inv_user = {v: k for k, v in user_id_map.items()}
    inv_item = {v: k for k, v in item_id_map.items()}

    user_values = [
        (inv_user[row], _matrix_to_vector_literal(user_embeddings[row]))
        for row in range(user_embeddings.shape[0])
        if row in inv_user
    ]
    item_values = [
        (inv_item[row], _matrix_to_vector_literal(item_embeddings[row]))
        for row in range(item_embeddings.shape[0])
        if row in inv_item
    ]

    with conn.cursor() as cur:
        if user_values:
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

        if item_values:
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


# ----------------------------
# Main
# ----------------------------

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

    db_url = args.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("--database_url or env DATABASE_URL must be provided")

    conn = ensure_connection(db_url)
    try:
        LOGGER.info("Fetching interactions and metadata from DB")
        interactions = fetch_interactions(
            conn,
            limit_users=args.limit_users,
            limit_interactions=args.limit_interactions,
        )
        if not interactions:
            raise SystemExit("No interactions found. Load data first.")
        LOGGER.info("Loaded %d interactions", len(interactions))

        item_to_genres = fetch_movies_and_genres(conn)

        dataset, user_id_map, item_id_map = build_dataset(interactions, item_to_genres)
        interactions_mtx, item_features = build_matrices(dataset, interactions, item_to_genres)

        LOGGER.info("Performing user-wise train/test split")
        train_mtx, test_mtx = train_test_split_by_user(interactions_mtx, test_fraction=args.test_fraction)

        LOGGER.info("Training LightFM model (WARP, %d components, %d epochs)", args.no_components, args.epochs)
        model = train_lightfm(
            train=train_mtx,
            item_features=item_features,
            no_components=args.no_components,
            epochs=args.epochs,
            num_threads=args.num_threads,
        )

        LOGGER.info("Evaluating Recall@%d", args.k)
        rec_lfm = recall_at_k(
            model,
            test_mtx,
            train_interactions=train_mtx,
            item_features=item_features,
            k=args.k,
            num_threads=args.num_threads,
        ).mean()
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
