"""
Negative-Control Diagnostic for the Synthesizer Label Leak.

On 2026-04-19 the feature-category ablation returned AUC=1.000 for the
'temporal' subset alone. Inspection of `data_loader.py` showed the cause:
`_generate_coordinated_times` and `_generate_organic_times` produce
cleanly separable inter-arrival distributions, and the branch is gated on
`news_item.is_fake`. The label is therefore baked into the cascade.

This script quantifies that leak with three conditions:

    baseline   : original synthesizer (label-dependent generator)
    shuffled   : same cascades, labels permuted before training
    neutral    : cascades generated with a single label-agnostic generator
                 (uses the 'organic' timing + averaged account priors for
                 every news item, regardless of its ground-truth label)

Expected outcome:
    baseline   -> AUC >> 0.5    (leak present)
    shuffled   -> AUC ~  0.5    (classifier has no signal)
    neutral    -> AUC ~  0.5    (generator-side signal removed)

The combination demonstrates that current AUC on this synthesizer reflects
generator behaviour, not detectable spread-pattern structure in
FakeNewsNet. Any positive claim requires either (a) a label-agnostic
synthesizer + external ground truth, or (b) real retweet traces.

Output: data/leak_diagnostic_<timestamp>.json
        figures/leak_diagnostic.{png,pdf}

Author: Claudio L. Lima
Date:   2026-04-21
"""

import json
import warnings
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from data_loader import FakeNewsNetLoader
from run_feature_ablation import (
    ALL_FEATURES,
    FEATURE_CATEGORIES,
    extract_matrix,
    subset_indices,
)
from spread_patterns import ContentCascade, ShareEvent, SpreadPatternExtractor

warnings.filterwarnings("ignore")


class NeutralFakeNewsNetLoader(FakeNewsNetLoader):
    """
    Loader that bypasses the label-dependent branch in the synthesizer.

    Every cascade is generated with the 'organic' timing distribution and
    the 'organic' account prior, regardless of whether the underlying
    news_item is fake or real. The ground-truth label is preserved on
    the ContentCascade (`is_synthetic`), so the classifier sees the true
    label but the input distribution is identical between classes.

    This is the clean control: if any feature category still yields
    AUC > 0.5, something other than the synthesizer is producing signal
    (e.g. tweet-count differences between fake/real news in the FNN CSV).
    """

    def _generate_synthetic_account_data(self, tweet_id, is_fake_news):
        # Ignore is_fake_news, always use the 'organic' prior
        return super()._generate_synthetic_account_data(tweet_id, is_fake_news=False)

    def _generate_cascade_structure(self, news_item):
        # Patch the timing generator by temporarily marking every item as real
        # for cascade construction, then restoring the true label on the
        # returned ContentCascade.
        true_is_fake = news_item.is_fake
        try:
            news_item.label = "real"  # forces organic generators inside super()
            cascade = super()._generate_cascade_structure(news_item)
        finally:
            news_item.label = "fake" if true_is_fake else "real"
        cascade.is_synthetic = true_is_fake  # restore ground truth
        return cascade


def evaluate(X: np.ndarray, y: np.ndarray, n_folds: int = 5, seed: int = 42) -> Dict:
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


def build_matrix(
    loader_cls,
    n_samples: int,
    source: str = None,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    loader = loader_cls()
    loader._rng = np.random.default_rng(seed)
    loader.download_minimal()
    loader.load_news_items()
    cascades = list(
        loader.generate_cascades(
            n_samples=n_samples, source=source, balanced=True, min_tweets=10
        )
    )
    extractor = SpreadPatternExtractor()
    return extract_matrix(cascades, extractor)


def run_condition(
    name: str,
    X: np.ndarray,
    y: np.ndarray,
    categories: List[str],
    n_folds: int = 5,
) -> Dict:
    print(f"\n{'=' * 70}\nCondition: {name}\n{'=' * 70}")
    print(f"  X={X.shape}  y_pos_rate={y.mean():.3f}")
    results = {}
    # Per-category-subset AUC (single categories + full union)
    category_subsets = [(c,) for c in categories] + [tuple(categories)]
    for combo in category_subsets:
        cols = subset_indices(combo)
        X_sub = X[:, cols]
        metrics = evaluate(X_sub, y, n_folds=n_folds)
        gb_auc = metrics["GradientBoosting"]["auc"][0]
        gb_f1 = metrics["GradientBoosting"]["f1"][0]
        lr_auc = metrics["LogisticRegression"]["auc"][0]
        label = "+".join(combo)
        print(
            f"  {label:40s}  GB AUC={gb_auc:.3f}  GB F1={gb_f1:.3f}  "
            f"LR AUC={lr_auc:.3f}"
        )
        results[label] = {
            "gb_auc_mean": gb_auc,
            "gb_auc_std": metrics["GradientBoosting"]["auc"][1],
            "gb_f1_mean": gb_f1,
            "lr_auc_mean": lr_auc,
        }
    return results


def plot_diagnostic(results: Dict, out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conditions = list(results.keys())
    category_labels = list(FEATURE_CATEGORIES.keys()) + ["all"]

    # For each category, collect GB AUC per condition
    data = {cat: [] for cat in category_labels}
    for cat in category_labels:
        key = cat if cat != "all" else "+".join(FEATURE_CATEGORIES.keys())
        for cond in conditions:
            data[cat].append(results[cond][key]["gb_auc_mean"])

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(conditions))
    width = 0.16
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#8c564b"]

    for i, cat in enumerate(category_labels):
        offset = (i - len(category_labels) / 2) * width + width / 2
        ax.bar(x + offset, data[cat], width, label=cat, color=colors[i])

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8, label="chance")
    ax.set_xticks(x)
    ax.set_xticklabels(conditions)
    ax.set_ylabel("GradientBoosting AUC (5-fold mean)")
    ax.set_ylim(0.0, 1.05)
    ax.set_title("Synthesizer label-leak diagnostic (FakeNewsNet)")
    ax.legend(loc="lower left", ncol=3, fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "leak_diagnostic.png", dpi=150)
    fig.savefig(out_dir / "leak_diagnostic.pdf")
    print(f"\nFigure saved: {out_dir / 'leak_diagnostic.png'}")


def main(n_samples: int = 600, n_folds: int = 5, seed: int = 42) -> None:
    categories = list(FEATURE_CATEGORIES.keys())
    all_results: Dict[str, Dict] = {}

    # --- baseline: original (label-dependent) synthesizer
    X_base, y_base = build_matrix(FakeNewsNetLoader, n_samples, seed=seed)
    all_results["baseline"] = run_condition(
        "baseline (label-dependent synthesizer)", X_base, y_base, categories, n_folds
    )

    # --- shuffled labels on the same baseline cascades
    rng = np.random.default_rng(seed + 1)
    y_shuf = y_base.copy()
    rng.shuffle(y_shuf)
    all_results["shuffled"] = run_condition(
        "shuffled (baseline X, permuted labels)", X_base, y_shuf, categories, n_folds
    )

    # --- neutral: label-agnostic synthesizer, true labels
    X_neu, y_neu = build_matrix(NeutralFakeNewsNetLoader, n_samples, seed=seed)
    all_results["neutral"] = run_condition(
        "neutral (label-agnostic synthesizer)", X_neu, y_neu, categories, n_folds
    )

    # --- summary
    print("\n" + "=" * 70)
    print("Summary (GB AUC, 'all-categories' subset)")
    print("=" * 70)
    full_key = "+".join(categories)
    for cond, res in all_results.items():
        auc = res[full_key]["gb_auc_mean"]
        delta = auc - 0.5
        verdict = "LEAK" if delta > 0.10 else "≈chance"
        print(f"  {cond:12s}  AUC={auc:.3f}  Δchance={delta:+.3f}  [{verdict}]")

    # --- save results
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_file = data_dir / f"leak_diagnostic_{stamp}.json"
    payload = {
        "config": {
            "n_samples": n_samples,
            "n_folds": n_folds,
            "seed": seed,
            "categories": {c: FEATURE_CATEGORIES[c] for c in categories},
        },
        "results": all_results,
        "notes": (
            "Three-condition diagnostic. 'baseline' uses the label-dependent "
            "synthesizer in data_loader.py. 'shuffled' permutes labels on the "
            "baseline feature matrix. 'neutral' uses NeutralFakeNewsNetLoader "
            "(organic generator for all items, true labels retained)."
        ),
    }
    with open(out_file, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nResults saved: {out_file}")

    plot_diagnostic(all_results, Path("figures"))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--n_samples", type=int, default=600)
    ap.add_argument("--n_folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    main(n_samples=args.n_samples, n_folds=args.n_folds, seed=args.seed)
