"""Streamlit dashboard for manual and near-live CICFlowMeter IDS predictions."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from ids_scoring import score_multiclass


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "models" / "cicids2017_multiclass_random_forest.joblib"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
LIVE_PREDICTIONS = OUTPUT_DIR / "live_flow_predictions.csv"
LIVE_STATUS = OUTPUT_DIR / "live_watcher_status.json"


@st.cache_resource
def load_bundle() -> dict:
    return joblib.load(MODEL_PATH)


def read_status() -> dict:
    if not LIVE_STATUS.exists():
        return {"status": "Live watcher has not been started."}
    try:
        return json.loads(LIVE_STATUS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "Waiting for watcher status..."}


def prediction_first(frame: pd.DataFrame) -> pd.DataFrame:
    # Put the IDS decision fields first so alerts are immediately visible.
    priority = [
        "IDS Prediction", "Confidence", "Requires Review",
        "Capture File", "Flow Row", "Scored At UTC",
    ]
    first = [column for column in priority if column in frame.columns]
    remaining = [column for column in frame.columns if column not in first]
    return frame[first + remaining]


def live_monitor() -> None:
    status = read_status()
    st.caption(status.get("status", "Waiting for live watcher"))
    if status.get("capture_file"):
        st.caption(f"Capture source: {status['capture_file']}")

    if not LIVE_PREDICTIONS.exists():
        st.info("No live predictions yet. Start CICFlowMeter, then run watch_live_flows.py in another terminal.")
        return
    try:
        history = pd.read_csv(LIVE_PREDICTIONS, low_memory=False)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        st.info("Waiting for the watcher to finish writing predictions...")
        return
    if history.empty:
        st.info("The watcher has not received any completed flows yet.")
        return

    alerts = history[history["Requires Review"].eq("Yes")]
    one, two, three = st.columns(3)
    one.metric("Flows scored", f"{len(history):,}")
    two.metric("Flows requiring review", f"{len(alerts):,}")
    three.metric("Latest category", str(history.iloc[-1]["IDS Prediction"]))

    st.subheader("Latest flow predictions")
    categories = sorted(history["IDS Prediction"].dropna().unique())
    selected_categories = st.multiselect(
        "Filter by IDS prediction",
        categories,
        default=categories,
        key="live_prediction_filter",
    )
    filtered = history[history["IDS Prediction"].isin(selected_categories)]
    st.dataframe(prediction_first(filtered.tail(100).iloc[::-1]), use_container_width=True)
    st.download_button(
        "Download live prediction history",
        history.to_csv(index=False).encode("utf-8"),
        file_name="live_flow_predictions.csv",
        mime="text/csv",
    )
    st.caption("Predictions are ML alerts for review, not proof of an intrusion.")


st.set_page_config(page_title="Realtime IDS", page_icon="🛡️", layout="wide")
st.title("🛡️ Realtime Network IDS")
st.caption("CICFlowMeter completed flows → multiclass Random Forest predictions")

if not MODEL_PATH.exists():
    st.error("No multiclass Random Forest model found. Run train_multiclass_model.py first.")
    st.stop()

live_tab, upload_tab = st.tabs(["Live monitor", "Score a CSV manually"])

with live_tab:
    # Streamlit 1.60 supports fragments, allowing this part to refresh without
    # requiring the user to upload or click anything.
    @st.fragment(run_every="5s")
    def auto_refresh_live_monitor() -> None:
        live_monitor()
    auto_refresh_live_monitor()

with upload_tab:
    uploaded = st.file_uploader("Upload a CICFlowMeter flow CSV", type="csv")
    if uploaded is None:
        st.info("Choose a CSV to score it once with the multiclass model.")
    else:
        raw = pd.read_csv(uploaded, low_memory=False)
        result, missing = score_multiclass(raw, load_bundle())
        alerts = result["Requires Review"].eq("Yes")
        one, two, three = st.columns(3)
        one.metric("Flows analysed", f"{len(result):,}")
        two.metric("Flows requiring review", f"{alerts.sum():,}")
        three.metric("Latest category", str(result.iloc[-1]["IDS Prediction"]))
        if missing:
            st.warning(f"{len(missing)} expected model features were unavailable and treated as unknown.")
        else:
            st.success("All required model features were found in this CSV.")
        categories = sorted(result["IDS Prediction"].dropna().unique())
        selected_categories = st.multiselect(
            "Filter by IDS prediction",
            categories,
            default=categories,
            key="uploaded_prediction_filter",
        )
        st.dataframe(
            prediction_first(
                result[result["IDS Prediction"].isin(selected_categories)]
                .sort_values("Confidence", ascending=False)
                .head(100)
            ),
            use_container_width=True,
        )
        st.download_button(
            "Download predictions CSV",
            result.to_csv(index=False).encode("utf-8"),
            file_name="ids_predictions.csv",
            mime="text/csv",
        )
