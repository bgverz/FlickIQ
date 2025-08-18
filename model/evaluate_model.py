"""
Evaluate LightFM model performance vs. a popularity baseline.

This script can either:
1) Re-train a LightFM model on-the-fly and evaluate Recall@K, or
2) Evaluate precomputed embeddings (user/item) using cosine similarity to compute recommendations and Recall@K.

Usage examples:
    python model/evaluate_model.py --train --epochs 5 --no_components 64
    python model/evaluate_model.py --from-db --k 10 --limit_users 5000
"""

import argparse
import logging
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import psycopg2
from scipy import sparse
from lightfm import LightFM
from lightfm.evaluation import recall_at_k

from model.train_model import (
    ensure_connection,
    fetch_movies_and_genres,
    fetch_interactions,
    build_dataset,
    build_matrices,
    train_test_split_by_user,
    train_lightfm,
)


LOGGER = logging.getLogger("evaluate_model")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def load_embeddings(conn) -> Tuple[Dict[int, np.ndarray], Dict[int, np.ndarray]]:
    user_vecs: Dict[int, np.ndarray] = {}
    item_vecs: Dict[int, np.ndarray] = {}
    with conn.cursor() as cur:
        cur.execute("SELECT user_id, embedding FROM user_embeddings")
        for uid, emb in cur.fetchall():
            vec = np.array([float(x) for x in emb.strip("[]").split(",")], dtype=np.float32)
            user_vecs[int(uid)] = vec
        cur.execute("SELECT movie_id, embedding FROM item_embeddings")
        for iid, emb in cur.fetchall():
            vec = np.array([float(x) for x in emb.strip("[]").split(",")], dtype=np.float32)
            item_vecs[int(iid)] = vec
    return user_vecs, item_vecs


def cosine_similarity_topk(user_vec: np.ndarray, item_matrix: np.ndarray, k: int) -> List[int]:
    uv = user_vec / (np.linalg.norm(user_vec) + 1e-12)
    im = item_matrix / (np.linalg.norm(item_matrix, axis=1, keepdims=True) + 1e-12)
    scores = im @ uv
    topk_idx = np.argsort(-scores)[:k]
    return topk_idx.tolist()


def evaluate_embeddings(conn, k: int, limit_users: Optional[int] = None) -> float:
    user_vecs, item_vecs = load_embeddings(conn)
    if not user_vecs or not item_vecs:
        raise SystemExit("Embeddings not found in DB. Train and save them first.")

    # Build mappings
    item_ids = sorted(item_vecs.keys())
    item_matrix = np.vstack([item_vecs[i] for i in item_ids])
    item_id_to_row = {iid: idx for idx, iid in enumerate(item_ids)}

    # Build ground truth from interactions
    interactions = fetch_interactions(conn, limit_users=limit_users)
    if not interactions:
        return 0.0
    by_user: Dict[int, List[int]] = {}
    for uid, iid, _w in interactions:
        by_user.setdefault(uid, []).append(iid)

    # Simple split for eval: last item as test
    recalls: List[float] = []
    for uid, items in by_user.items():
        if uid not in user_vecs or len(items) < 2:
            continue
        test_item = items[-1]
        train_items = set(items[:-1])
        # Recommend top-k excluding known train items
        topk_rows = cosine_similarity_topk(user_vecs[uid], item_matrix, k + len(train_items))
        topk_iids = []
        for row in topk_rows:
            iid = item_ids[row]
            if iid not in train_items:
                topk_iids.append(iid)
            if len(topk_iids) >= k:
                break
        hit = 1.0 if test_item in topk_iids else 0.0
        recalls.append(hit)
    return float(np.mean(recalls)) if recalls else 0.0


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Evaluate LightFM vs popularity baseline")
    parser.add_argument("--database_url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--train", action="store_true", help="Train a model now for evaluation")
    parser.add_argument("--from-db", action="store_true", help="Evaluate using saved embeddings")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--no_components", type=int, default=64)
    parser.add_argument("--num_threads", type=int, default=8)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--limit_users", type=int, default=None)
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("--database_url or env DATABASE_URL must be provided")

    conn = ensure_connection(args.database_url)
    try:
        if args.train:
            interactions = fetch_interactions(conn, limit_users=args.limit_users)
            if not interactions:
                raise SystemExit("No interactions found")
            item_to_genres = fetch_movies_and_genres(conn)
            dataset, _, _ = build_dataset(interactions, item_to_genres)
            inter_mtx, item_feats = build_matrices(dataset, interactions, item_to_genres)
            train_mtx, test_mtx = train_test_split_by_user(inter_mtx)
            model = train_lightfm(train_mtx, item_feats, args.no_components, args.epochs, args.num_threads)
            rec = recall_at_k(model, test_mtx, train_interactions=train_mtx, item_features=item_feats, k=args.k, num_threads=args.num_threads).mean()
            LOGGER.info("LightFM Recall@%d: %.4f", args.k, float(rec))
        if args.from_db:
            rec = evaluate_embeddings(conn, k=args.k, limit_users=args.limit_users)
            LOGGER.info("Embeddings Recall@%d: %.4f", args.k, float(rec))
    finally:
        conn.close()


if __name__ == "__main__":
    main()


