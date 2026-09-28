#!/usr/bin/env python3
"""Measured numeric regression baseline using spatial BLOCK cross-validation.

Consumes only the researcher's CSV: there are no synthetic or claimed benchmark results.
Optional dependencies: pandas, numpy, scikit-learn.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(csv: str, target: str, features: list[str], lat: str, lon: str,
        block_size: float, folds: int, seed: int) -> dict:
    try:
        import numpy as np
        import pandas as pd
        import sklearn
        from sklearn.dummy import DummyRegressor
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        from sklearn.model_selection import GroupKFold
    except ImportError as exc:
        raise RuntimeError("Install optional requirements: pip install -r requirements-experiments.txt") from exc
    if block_size <= 0 or folds < 2 or not features:
        raise ValueError("Block size must be positive; folds >=2; at least one feature.")
    if len(set(features)) != len(features) or target in features:
        raise ValueError("Duplicate predictors or target leakage in --features.")
    path = Path(csv)
    raw = path.read_bytes()
    frame = pd.read_csv(path)
    required = list(dict.fromkeys(features + [target, lat, lon]))
    absent = [col for col in required if col not in frame]
    if absent:
        raise ValueError("Missing required CSV columns: " + ", ".join(absent))
    clean = frame.loc[:, required].copy()
    for col in required:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
    clean = clean.replace([np.inf, -np.inf], np.nan).dropna()
    clean = clean[(clean[lat].between(-90, 90)) & (clean[lon].between(-180, 180))]
    if len(clean) < 25:
        raise ValueError("Need >=25 complete numeric rows with valid coordinates.")
    x = clean[features].to_numpy(dtype=float)
    y = clean[target].to_numpy(dtype=float)
    g_lat = np.floor((clean[lat].to_numpy() + 90) / block_size).astype(int)
    g_lon = np.floor((clean[lon].to_numpy() + 180) / block_size).astype(int)
    groups = (pd.Series(g_lat).astype(str) + ":" + pd.Series(g_lon).astype(str)).to_numpy()
    n_groups = len(np.unique(groups))
    if n_groups < 2:
        raise ValueError("Need at least 2 distinct spatial grid cells; reduce --block-size.")
    n_splits = min(folds, n_groups)
    cross_validation = GroupKFold(n_splits=n_splits)
    reports = []
    for i, (train_idx, test_idx) in enumerate(cross_validation.split(x, y, groups), start=1):
        if set(groups[train_idx]) & set(groups[test_idx]):
            raise AssertionError("Spatial leakage: training and test share spatial block.")
        baseline = DummyRegressor(strategy="median")
        model = RandomForestRegressor(n_estimators=100, min_samples_leaf=2, random_state=seed, n_jobs=1)
        entry = {"fold": i, "train_size": int(len(train_idx)), "test_size": int(len(test_idx)),
                 "train_blocks": int(len(set(groups[train_idx]))),
                 "test_blocks": int(len(set(groups[test_idx]))), "models": {}}
        for label, learner in [("dummy_median", baseline), ("random_forest", model)]:
            learner.fit(x[train_idx], y[train_idx])
            pred = learner.predict(x[test_idx])
            entry["models"][label] = {
                "mae": float(mean_absolute_error(y[test_idx], pred)),
                "rmse": float(math.sqrt(mean_squared_error(y[test_idx], pred))),
                "r2": float(r2_score(y[test_idx], pred)) if len(test_idx) >= 2 else None,
            }
        reports.append(entry)
    summary = {
        label: {
            metric: float(np.mean([row["models"][label][metric] for row in reports]))
            for metric in ("mae", "rmse")
        } for label in ("dummy_median", "random_forest")
    }
    return {
        "status": "computed-on-user-csv-not-independent-publication",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "input_csv_name": path.name,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "rows_total": int(len(frame)),
        "rows_used": int(len(clean)),
        "target": target, "features": features, "lat": lat, "lon": lon,
        "block_size_degrees": block_size, "spatial_blocks": n_groups,
        "cv_folds": n_splits, "seed": seed,
        "python": sys.version.split()[0], "numpy": np.__version__,
        "pandas": pd.__version__, "scikit_learn": sklearn.__version__,
        "summary": summary, "folds": reports,
        "caveat": (
            "Degrees are not equal-area distances; choose block size appropriate to latitude. "
            "GroupKFold avoids shared-grid leakage, not all spatial autocorrelation. "
            "Data representativeness, licensing and any claims of novelty require human checks."
        ),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--features", required=True)
    ap.add_argument("--lat", default="lat")
    ap.add_argument("--lon", default="lon")
    ap.add_argument("--block-size", type=float, default=0.25)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--output", default="outputs/latest/experiment.json")
    a = ap.parse_args()
    result = run(a.csv, a.target, [f.strip() for f in a.features.split(",") if f.strip()],
                 a.lat, a.lon, a.block_size, a.folds, a.seed)
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Computed real spatial-CV metrics:", dest)


if __name__ == "__main__":
    main()
