"""
Robustness check on the residual signal in the label-agnostic synthesizer.

The Apr 21 leak diagnostic (`run_leak_diagnostic.py`) showed that the
NeutralFakeNewsNetLoader (organic generator for every item, true labels
preserved) still yields GB AUC ~0.59 on the full feature set, n=600. The
question for the thesis is whether that ~0.09 above chance is a stable
real signal in FakeNewsNet — likely driven by tweet-count or account-prior
differences between fake and real news items in the FNN CSVs — or whether
it is noise from a single sample.

This script sweeps n_samples x seed on the neutral condition and reports
mean +/- std AUC across seeds. If the signal is real, AUC should be
roughly seed-invariant and trend-stable as n grows. If it is noise, AUC
should fluctuate widely across seeds.

Output: data/neutral_robustness_<timestamp>.json
        figures/neutral_robustness.{png,pdf}

Author: Claudio L. Lima
Date:   2026-04-28
"""

import argparse
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

from run_feature_ablation import (
    FEATURE_CATEGORIES,
    extract_matrix,
    subset_indices,
)
from run_leak_diagnostic import NeutralFakeNewsNetLoader
from spread_patterns import SpreadPatternExtractor

warnings.filterwarnings("ignore")


def _evaluate_subset(X: np.ndarray, y: np.ndarray, n_folds: int, seed: int) -> Dict:
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    out = defaultdict(list)
    for tr, te in cv.split(X, y):
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[tr])
        X_te = scaler.transform(X[te])

        gb = GradientBoostingClassifier(n_estimators=100, random_state=seed)
        gb.fit(X_tr, y[tr])
        gb_prob = gb.predict_proba(X_te)[:, 1]
        gb_pred = (gb_prob >= 0.5).astype(int)
        out["gb_auc"].append(roc_auc_score(y[te], gb_prob))
        out["gb_f1"].append(f1_score(y[te], gb_pred))

        lr = LogisticRegression(max_iter=1000, class_weight="balanced")
        lr.fit(X_tr, y[tr])
        lr_prob = lr.predict_proba(X_te)[:, 1]
        out["lr_auc"].append(roc_auc_score(y[te], lr_prob))

    return {k: float(np.mean(v)) for k, v in out.items()}


def build_neutral_matrix(n_samples: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    loader = NeutralFakeNewsNetLoader()
    loader._rng = np.random.default_rng(seed)
    loader.download_minimal()
    loader.load_news_items()
    cascades = list(
        loader.generate_cascades(
            n_samples=n_samples, source=None, balanced=True, min_tweets=10
        )
    )
    extractor = SpreadPatternExtractor()
    return extract_matrix(cascades, extractor)


def run_sweep(
    sizes: List[int], seeds: List[int], n_folds: int
) -> Dict[int, Dict[str, List[float]]]:
    categories = list(FEATURE_CATEGORIES.keys())
    full_cols = subset_indices(categories)
    results: Dict[int, Dict[str, List[float]]] = {}

    for n in sizes:
        per_n = defaultdict(list)
        for seed in seeds:
            print(f"  n_samples={n:5d}  seed={seed} ...", end="", flush=True)
            X, y = build_neutral_matrix(n_samples=n, seed=seed)
            X_full = X[:, full_cols]
            metrics = _evaluate_subset(X_full, y, n_folds=n_folds, seed=seed)
            print(
                f"  GB AUC={metrics['gb_auc']:.3f}  "
                f"GB F1={metrics['gb_f1']:.3f}  "
                f"LR AUC={metrics['lr_auc']:.3f}"
            )
            for k, v in metrics.items():
                per_n[k].append(v)
            per_n["seeds"].append(seed)
        results[n] = dict(per_n)
    return results


def summarize(results: Dict[int, Dict[str, List[float]]]) -> Dict:
    summary = {}
    for n, per_n in results.items():
        summary[n] = {
            "gb_auc_mean": float(np.mean(per_n["gb_auc"])),
            "gb_auc_std": float(np.std(per_n["gb_auc"])),
            "gb_auc_min": float(np.min(per_n["gb_auc"])),
            "gb_auc_max": float(np.max(per_n["gb_auc"])),
            "gb_f1_mean": float(np.mean(per_n["gb_f1"])),
            "gb_f1_std": float(np.std(per_n["gb_f1"])),
            "lr_auc_mean": float(np.mean(per_n["lr_auc"])),
            "lr_auc_std": float(np.std(per_n["lr_auc"])),
            "n_seeds": len(per_n["seeds"]),
        }
    return summary


def plot_robustness(
    summary: Dict[int, Dict], raw: Dict[int, Dict], out_dir: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sizes = sorted(summary.keys())
    gb_means = [summary[n]["gb_auc_mean"] for n in sizes]
    gb_stds = [summary[n]["gb_auc_std"] for n in sizes]
    lr_means = [summary[n]["lr_auc_mean"] for n in sizes]
    lr_stds = [summary[n]["lr_auc_std"] for n in sizes]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(
        sizes,
        gb_means,
        yerr=gb_stds,
        fmt="-o",
        color="#1f77b4",
        label="GradientBoosting (mean ± std across seeds)",
        capsize=4,
    )
    ax.errorbar(
        sizes,
        lr_means,
        yerr=lr_stds,
        fmt="--s",
        color="#ff7f0e",
        label="LogisticRegression",
        capsize=4,
    )

    for n in sizes:
        for v in raw[n]["gb_auc"]:
            ax.scatter(n, v, color="#1f77b4", alpha=0.25, s=18, zorder=1)

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8, label="chance")
    ax.set_xscale("log")
    ax.set_xticks(sizes)
    ax.set_xticklabels([str(n) for n in sizes])
    ax.set_xlabel("n_samples (balanced)")
    ax.set_ylabel("5-fold CV AUC (full feature set)")
    ax.set_ylim(0.40, 0.85)
    ax.set_title(
        "Residual signal in label-agnostic synthesizer — FakeNewsNet"
    )
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "neutral_robustness.png", dpi=150)
    fig.savefig(out_dir / "neutral_robustness.pdf")
    print(f"\nFigure saved: {out_dir / 'neutral_robustness.png'}")


def main(sizes: List[int], seeds: List[int], n_folds: int) -> None:
    print("=" * 70)
    print("Neutral synthesizer robustness sweep")
    print("=" * 70)
    print(f"sizes={sizes}  seeds={seeds}  n_folds={n_folds}")

    raw = run_sweep(sizes, seeds, n_folds)
    summary = summarize(raw)

    print("\n" + "=" * 70)
    print(f"{'n_samples':>10s}  {'GB AUC mean±std':>18s}  "
          f"{'min':>6s}  {'max':>6s}  {'LR AUC mean±std':>18s}")
    print("-" * 70)
    for n in sorted(summary.keys()):
        s = summary[n]
        print(
            f"{n:>10d}  {s['gb_auc_mean']:.3f}±{s['gb_auc_std']:.3f}      "
            f"{s['gb_auc_min']:.3f}  {s['gb_auc_max']:.3f}  "
            f"{s['lr_auc_mean']:.3f}±{s['lr_auc_std']:.3f}"
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_file = data_dir / f"neutral_robustness_{stamp}.json"
    payload = {
        "config": {
            "sizes": sizes,
            "seeds": seeds,
            "n_folds": n_folds,
            "feature_categories": {c: FEATURE_CATEGORIES[c] for c in FEATURE_CATEGORIES},
        },
        "raw": {str(n): raw[n] for n in sorted(raw.keys())},
        "summary": {str(n): summary[n] for n in sorted(summary.keys())},
        "notes": (
            "Sweeps n_samples x seed on NeutralFakeNewsNetLoader to characterize "
            "the residual ~0.59 AUC observed in run_leak_diagnostic.py (Apr 21). "
            "Stability across seeds and sample sizes indicates whether the residual "
            "is a real (small) signal in FakeNewsNet or sampling noise."
        ),
    }
    with open(out_file, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nResults saved: {out_file}")

    plot_robustness(summary, raw, Path("figures"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[200, 400, 600, 1000],
    )
    ap.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[42, 43, 44, 45, 46],
    )
    ap.add_argument("--n_folds", type=int, default=5)
    args = ap.parse_args()
    main(sizes=args.sizes, seeds=args.seeds, n_folds=args.n_folds)
