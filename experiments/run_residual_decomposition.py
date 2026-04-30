"""
Residual decomposition on the label-agnostic synthesizer.

The Apr 28 robustness sweep (`run_neutral_robustness.py`) confirmed that
the NeutralFakeNewsNetLoader produces a small but stable GB AUC ~0.61
on the full 27-feature spread-pattern set, even after the timing-based
label leak is patched.

The two prime suspects (from Apr 28 notes):
  1. tweet-count-derived features that mirror len(news_item.tweet_ids)
     differences between fake and real items in the FakeNewsNet CSVs:
        {total_shares, shares_per_hour}
  2. the account-prior block, where any residual fake/real asymmetry in
     the synthesized account distributions could survive the leak patch:
        the entire 'account' category

This script runs four ablations on neutral cascades (n=1000, 5 seeds):
    full              : all features (reference)
    drop_size         : full minus {total_shares, shares_per_hour}
    drop_account      : full minus 'account' category
    drop_size_account : full minus both

If `drop_size_account` AUC collapses to ~0.5, the residual is fully
localized to size + account priors and a methods footnote can be
written. Anything that survives points to a deeper, more interesting
residual that needs further decomposition.

Output: data/residual_decomposition_<timestamp>.json
        figures/residual_decomposition.{png,pdf}

Author: Claudio L. Lima
Date:   2026-04-30
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
    ALL_FEATURES,
    FEATURE_CATEGORIES,
    extract_matrix,
)
from run_leak_diagnostic import NeutralFakeNewsNetLoader
from spread_patterns import SpreadPatternExtractor

warnings.filterwarnings("ignore")


SIZE_FEATURES = ["total_shares", "shares_per_hour"]


def build_conditions() -> Dict[str, List[str]]:
    """Map condition name -> list of feature names retained."""
    full = list(ALL_FEATURES)
    account = list(FEATURE_CATEGORIES["account"])

    drop_size = [f for f in full if f not in SIZE_FEATURES]
    drop_account = [f for f in full if f not in account]
    drop_both = [f for f in full if f not in SIZE_FEATURES and f not in account]

    return {
        "full": full,
        "drop_size": drop_size,
        "drop_account": drop_account,
        "drop_size_account": drop_both,
    }


def column_mask(feature_subset: List[str]) -> List[int]:
    return [ALL_FEATURES.index(f) for f in feature_subset]


def evaluate_one(X: np.ndarray, y: np.ndarray, n_folds: int, seed: int) -> Dict:
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


def run(n_samples: int, seeds: List[int], n_folds: int) -> Dict:
    conditions = build_conditions()
    raw: Dict[str, Dict[str, List[float]]] = {
        name: defaultdict(list) for name in conditions
    }

    print("=" * 72)
    print("Residual decomposition on label-agnostic synthesizer")
    print("=" * 72)
    print(f"n_samples={n_samples}  seeds={seeds}  n_folds={n_folds}")
    print(f"size features: {SIZE_FEATURES}")
    print(f"account features ({len(FEATURE_CATEGORIES['account'])}): "
          f"{FEATURE_CATEGORIES['account']}")
    print()

    for seed in seeds:
        print(f"  seed={seed}: building neutral matrix (n={n_samples})...",
              end="", flush=True)
        X, y = build_neutral_matrix(n_samples=n_samples, seed=seed)
        print(f" X={X.shape}")
        for name, features in conditions.items():
            cols = column_mask(features)
            metrics = evaluate_one(X[:, cols], y, n_folds=n_folds, seed=seed)
            print(
                f"    {name:20s} (k={len(cols):2d})  "
                f"GB AUC={metrics['gb_auc']:.3f}  "
                f"GB F1={metrics['gb_f1']:.3f}  "
                f"LR AUC={metrics['lr_auc']:.3f}"
            )
            for k, v in metrics.items():
                raw[name][k].append(v)
            raw[name]["seed"].append(seed)
            raw[name]["k"] = len(cols)

    summary = {}
    for name, per in raw.items():
        summary[name] = {
            "k": per["k"],
            "gb_auc_mean": float(np.mean(per["gb_auc"])),
            "gb_auc_std": float(np.std(per["gb_auc"])),
            "gb_auc_min": float(np.min(per["gb_auc"])),
            "gb_auc_max": float(np.max(per["gb_auc"])),
            "gb_f1_mean": float(np.mean(per["gb_f1"])),
            "lr_auc_mean": float(np.mean(per["lr_auc"])),
            "lr_auc_std": float(np.std(per["lr_auc"])),
            "n_seeds": len(per["seed"]),
        }
    return {"raw": {k: dict(v) for k, v in raw.items()}, "summary": summary}


def print_summary(summary: Dict[str, Dict]) -> None:
    print("\n" + "=" * 72)
    print("Summary (5-fold CV AUC, mean ± std across seeds)")
    print("=" * 72)
    full_auc = summary["full"]["gb_auc_mean"]
    print(f"{'condition':22s} {'k':>3s}  {'GB AUC':>14s}  "
          f"{'min':>5s}  {'max':>5s}  {'Δ_full':>7s}  {'LR AUC':>14s}")
    print("-" * 80)
    order = ["full", "drop_size", "drop_account", "drop_size_account"]
    for name in order:
        s = summary[name]
        delta = s["gb_auc_mean"] - full_auc
        print(
            f"{name:22s} {s['k']:>3d}  "
            f"{s['gb_auc_mean']:.3f}±{s['gb_auc_std']:.3f}  "
            f"{s['gb_auc_min']:>.3f}  {s['gb_auc_max']:>.3f}  "
            f"{delta:+.3f}  "
            f"{s['lr_auc_mean']:.3f}±{s['lr_auc_std']:.3f}"
        )

    final_auc = summary["drop_size_account"]["gb_auc_mean"]
    final_delta = final_auc - 0.5
    print()
    if final_delta < 0.02:
        verdict = "RESOLVED — residual fully localized to size + account priors"
    elif final_delta < 0.05:
        verdict = "MOSTLY RESOLVED — small residual remains, likely sampling noise"
    else:
        verdict = "UNRESOLVED — residual survives, needs deeper decomposition"
    print(f"drop_size_account AUC = {final_auc:.3f} (Δ_chance = {final_delta:+.3f})")
    print(f"Verdict: {verdict}")


def plot(summary: Dict[str, Dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = ["full", "drop_size", "drop_account", "drop_size_account"]
    labels = ["full\n(27)", "drop_size\n(-2)", "drop_account\n(-9)",
              "drop_size+account\n(-11)"]
    colors = ["#1f77b4", "#7fc97f", "#fdc086", "#d62728"]

    gb_means = [summary[n]["gb_auc_mean"] for n in order]
    gb_stds = [summary[n]["gb_auc_std"] for n in order]
    lr_means = [summary[n]["lr_auc_mean"] for n in order]
    lr_stds = [summary[n]["lr_auc_std"] for n in order]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(order))
    width = 0.38

    bars_gb = ax.bar(
        x - width / 2, gb_means, width, yerr=gb_stds,
        color=colors, edgecolor="black", capsize=4,
        label="GradientBoosting",
    )
    ax.bar(
        x + width / 2, lr_means, width, yerr=lr_stds,
        color=colors, alpha=0.55, edgecolor="black", capsize=4, hatch="//",
        label="LogisticRegression",
    )

    for bar, m in zip(bars_gb, gb_means):
        ax.text(
            bar.get_x() + bar.get_width() / 2, m + 0.015, f"{m:.3f}",
            ha="center", va="bottom", fontsize=9,
        )

    ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.8, label="chance")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("5-fold CV AUC (mean ± std across seeds)")
    ax.set_ylim(0.45, 0.72)
    ax.set_title(
        "Residual decomposition on neutral synthesizer (FakeNewsNet, n=1000)"
    )
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "residual_decomposition.png", dpi=150)
    fig.savefig(out_dir / "residual_decomposition.pdf")
    print(f"\nFigure saved: {out_dir / 'residual_decomposition.png'}")


def main(n_samples: int, seeds: List[int], n_folds: int) -> None:
    payload = run(n_samples=n_samples, seeds=seeds, n_folds=n_folds)
    print_summary(payload["summary"])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_file = data_dir / f"residual_decomposition_{stamp}.json"

    serializable_raw = {}
    for name, per in payload["raw"].items():
        serializable_raw[name] = {
            k: (v if not isinstance(v, list) else [float(x) for x in v])
            for k, v in per.items()
        }

    with open(out_file, "w") as fh:
        json.dump(
            {
                "config": {
                    "n_samples": n_samples,
                    "seeds": seeds,
                    "n_folds": n_folds,
                    "size_features": SIZE_FEATURES,
                    "account_features": FEATURE_CATEGORIES["account"],
                },
                "raw": serializable_raw,
                "summary": payload["summary"],
                "notes": (
                    "Residual decomposition: ablate size and account-prior "
                    "feature blocks on the label-agnostic synthesizer to "
                    "localize the source of the ~0.61 AUC residual found in "
                    "the Apr 28 robustness sweep."
                ),
            },
            fh,
            indent=2,
        )
    print(f"Results saved: {out_file}")

    plot(payload["summary"], Path("figures"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n_samples", type=int, default=1000)
    ap.add_argument(
        "--seeds", type=int, nargs="+", default=[42, 43, 44, 45, 46]
    )
    ap.add_argument("--n_folds", type=int, default=5)
    args = ap.parse_args()
    main(n_samples=args.n_samples, seeds=args.seeds, n_folds=args.n_folds)
