"""
Feature-Category Ablation on FakeNewsNet.

Spread-pattern features partition into four theoretical categories:
    temporal, cascade, account, coordination.

This script measures the contribution of each category (and every non-empty
combination of categories) to classification performance. It mirrors the
ablation pattern used by HAVIC (Peng et al., 2026) for audio-visual
coherence heads: isolate each signal, then recombine.

Output: data/ablation_results_<timestamp>.json
        plus a printed table of AUC / F1 per category subset.

Author: Claudio L. Lima
Date: 2026-04-19
"""

import json
import itertools
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from data_loader import FakeNewsNetLoader
from spread_patterns import SpreadPatternExtractor

warnings.filterwarnings("ignore")


FEATURE_CATEGORIES = {
    "temporal": [
        "time_to_first_share_seconds",
        "total_shares",
        "shares_per_hour",
        "mean_inter_share_seconds",
        "std_inter_share_seconds",
        "inter_share_cv",
        "burstiness",
        "peak_hour",
    ],
    "cascade": [
        "cascade_depth",
        "cascade_breadth",
        "depth_to_breadth_ratio",
        "structural_virality",
        "direct_reshare_fraction",
        "deep_share_fraction",
    ],
    "account": [
        "mean_account_age_days",
        "std_account_age_days",
        "new_account_fraction",
        "mean_follower_count",
        "std_follower_count",
        "small_account_fraction",
        "mean_following_count",
        "verified_fraction",
        "mean_follower_following_ratio",
    ],
    "coordination": [
        "temporal_clustering_score",
        "account_age_clustering",
    ],
}

ALL_FEATURES = [f for feats in FEATURE_CATEGORIES.values() for f in feats]


def extract_matrix(cascades, extractor):
    X, y = [], []
    for cascade in cascades:
        feats = extractor.extract_all_features(cascade)
        row = []
        for name in ALL_FEATURES:
            v = feats.get(name, 0)
            if v == float("inf"):
                v = 1e6
            elif v == float("-inf"):
                v = -1e6
            elif np.isnan(v):
                v = 0
            row.append(v)
        X.append(row)
        y.append(1 if cascade.is_synthetic else 0)
    return np.array(X), np.array(y)


def subset_indices(category_subset):
    """Column indices in ALL_FEATURES for the given category names."""
    keep = []
    for cat in category_subset:
        for name in FEATURE_CATEGORIES[cat]:
            keep.append(ALL_FEATURES.index(name))
    return keep


def evaluate(X, y, n_folds=5, seed=42):
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    classifiers = {
        "LogisticRegression": lambda: LogisticRegression(
            max_iter=1000, class_weight="balanced"
        ),
        "GradientBoosting": lambda: GradientBoostingClassifier(
            n_estimators=100, random_state=seed
        ),
    }
    out = {name: defaultdict(list) for name in classifiers}
    for tr, te in cv.split(X, y):
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[tr])
        X_te = scaler.transform(X[te])
        for name, make in classifiers.items():
            clf = make()
            clf.fit(X_tr, y[tr])
            prob = clf.predict_proba(X_te)[:, 1]
            pred = (prob >= 0.5).astype(int)
            out[name]["auc"].append(roc_auc_score(y[te], prob))
            out[name]["f1"].append(f1_score(y[te], pred))
    return {
        name: {m: (float(np.mean(v)), float(np.std(v))) for m, v in metrics.items()}
        for name, metrics in out.items()
    }


def all_nonempty_subsets(categories):
    cats = list(categories)
    for r in range(1, len(cats) + 1):
        for combo in itertools.combinations(cats, r):
            yield combo


def run(n_samples=1200, n_folds=5, source=None, output_dir="data"):
    print("=" * 70)
    print("FakeNewsNet Feature-Category Ablation")
    print("=" * 70)
    print(f"n_samples={n_samples} n_folds={n_folds} source={source}")

    loader = FakeNewsNetLoader()
    extractor = SpreadPatternExtractor()
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    print("\nLoading dataset...")
    loader.download_minimal()
    loader.load_news_items()

    print("Generating cascades...")
    cascades = list(
        loader.generate_cascades(
            n_samples=n_samples, source=source, balanced=True, min_tweets=10
        )
    )
    fake = sum(1 for c in cascades if c.is_synthetic)
    print(f"  total={len(cascades)}  fake={fake}  real={len(cascades)-fake}")

    print("Extracting features...")
    X, y = extract_matrix(cascades, extractor)
    print(f"  X={X.shape}  y={y.shape}")

    subsets = list(all_nonempty_subsets(FEATURE_CATEGORIES.keys()))
    print(f"\nEvaluating {len(subsets)} category subsets...\n")

    table_rows = []
    all_results = []
    for combo in subsets:
        cols = subset_indices(combo)
        X_sub = X[:, cols]
        metrics = evaluate(X_sub, y, n_folds=n_folds)
        label = "+".join(combo)
        gb = metrics["GradientBoosting"]
        lr = metrics["LogisticRegression"]
        table_rows.append(
            (
                label,
                len(cols),
                gb["auc"][0],
                gb["auc"][1],
                gb["f1"][0],
                lr["auc"][0],
            )
        )
        all_results.append(
            {
                "categories": list(combo),
                "n_features": len(cols),
                "metrics": metrics,
            }
        )

    table_rows.sort(key=lambda r: r[2], reverse=True)
    print(f"{'subset':55s} {'k':>3s}  {'GB AUC':>9s}  {'GB F1':>7s}  {'LR AUC':>7s}")
    print("-" * 90)
    for label, k, gb_auc, gb_std, gb_f1, lr_auc in table_rows:
        print(
            f"{label:55s} {k:3d}  {gb_auc:.3f}±{gb_std:.2f}  "
            f"{gb_f1:.3f}    {lr_auc:.3f}"
        )

    print("\nPer-category marginal AUC (GB, single-category subsets):")
    singles = {r[0]: r[2] for r in table_rows if "+" not in r[0]}
    for cat, auc in sorted(singles.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {cat:15s} {auc:.3f}")

    full_auc = next(r[2] for r in table_rows if r[0].count("+") == 3)
    print(f"\nFull (all 4 categories) GB AUC: {full_auc:.3f}")
    for cat in FEATURE_CATEGORIES:
        ablated = "+".join(c for c in FEATURE_CATEGORIES if c != cat)
        ablated_auc = next(r[2] for r in table_rows if r[0] == ablated)
        delta = full_auc - ablated_auc
        print(f"  drop '{cat:13s}' -> {ablated_auc:.3f}  (Δ = {delta:+.3f})")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_path / f"ablation_results_{stamp}.json"
    payload = {
        "config": {
            "n_samples": n_samples,
            "n_folds": n_folds,
            "source": source,
            "categories": {c: FEATURE_CATEGORIES[c] for c in FEATURE_CATEGORIES},
        },
        "results": all_results,
    }
    with open(out_file, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nSaved: {out_file}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--n_samples", type=int, default=1200)
    ap.add_argument("--n_folds", type=int, default=5)
    ap.add_argument("--source", type=str, default=None)
    ap.add_argument("--output_dir", type=str, default="data")
    args = ap.parse_args()
    run(
        n_samples=args.n_samples,
        n_folds=args.n_folds,
        source=args.source,
        output_dir=args.output_dir,
    )
