"""Shared feature alignment and multiclass scoring helpers for the IDS."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd


FEATURE_ALIASES = {
    "min_packet_length": "packet_length_min",
    "max_packet_length": "packet_length_max",
    "cwe_flag_count": "cwr_flag_count",
    "avg_fwd_segment_size": "fwd_segment_size_avg",
    "avg_bwd_segment_size": "bwd_segment_size_avg",
    "fwd_avg_bytes_bulk": "fwd_bytes_bulk_avg",
    "fwd_avg_packet_bulk": "fwd_packet_bulk_avg",
    "fwd_avg_bulk_rate": "fwd_bulk_rate_avg",
    "bwd_avg_bytes_bulk": "bwd_bytes_bulk_avg",
    "bwd_avg_packet_bulk": "bwd_packet_bulk_avg",
    "bwd_avg_bulk_rate": "bwd_bulk_rate_avg",
    "init_win_bytes_fwd": "fwd_init_win_bytes",
    "init_win_bytes_bwd": "bwd_init_win_bytes",
    "act_data_pkt_fwd": "fwd_act_data_pkts",
    "min_seg_size_fwd": "fwd_seg_size_min",
}


def canonical_name(name: str) -> str:
    name = name.strip().lower()
    name = name.replace("forward", "fwd").replace("backward", "bwd")
    name = name.replace("packets", "packet")
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def feature_names(bundle: dict) -> list[str]:
    names = bundle.get("feature_columns", bundle.get("feature_names"))
    if not names:
        raise KeyError("The model bundle did not contain feature names.")
    return list(names)


def align_features(raw: pd.DataFrame, names: list[str]) -> tuple[pd.DataFrame, list[str]]:
    source_columns = {canonical_name(column): column for column in raw.columns}
    aligned = pd.DataFrame(index=raw.index)
    missing: list[str] = []
    for feature in names:
        source = source_columns.get(feature)
        if source is None:
            source = source_columns.get(FEATURE_ALIASES.get(feature, ""))
        if source is None:
            aligned[feature] = np.nan
            missing.append(feature)
        else:
            aligned[feature] = pd.to_numeric(raw[source], errors="coerce")
    return aligned.replace([np.inf, -np.inf], np.nan), missing


def score_multiclass(raw: pd.DataFrame, bundle: dict) -> tuple[pd.DataFrame, list[str]]:
    """Return original flow rows with a category and confidence for each flow."""
    names = feature_names(bundle)
    features, missing = align_features(raw, names)
    model = bundle["model"]
    # The Random Forest was fitted from a NumPy array after imputation, so pass
    # the aligned values without DataFrame names during inference as well.
    probabilities = model.predict_proba(features.to_numpy())
    indexes = probabilities.argmax(axis=1)
    classes = list(model.classes_)

    result = raw.copy()
    result["IDS Prediction"] = [classes[index] for index in indexes]
    result["Confidence"] = probabilities.max(axis=1).round(4)
    result["Requires Review"] = np.where(result["IDS Prediction"].eq("Benign"), "No", "Yes")
    return result, missing
