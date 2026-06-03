import io
from datetime import date

import pandas as pd
import streamlit as st

_COLUMNS = ["program_name", "signal_required_explicit", "verbatim_quote", "source_url", "checked_date"]


def init_store():
    if "results" not in st.session_state:
        st.session_state["results"] = pd.DataFrame(columns=_COLUMNS)


def find_cached(program_name: str) -> dict | None:
    df: pd.DataFrame = st.session_state["results"]
    if df.empty:
        return None
    match = df[df["program_name"].str.strip().str.lower() == program_name.strip().lower()]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def save_result(result_dict: dict):
    df: pd.DataFrame = st.session_state["results"]
    program_name = result_dict.get("program", result_dict.get("program_name", ""))
    row = {
        "program_name": program_name,
        "signal_required_explicit": result_dict.get("signal_required_explicit"),
        "verbatim_quote": result_dict.get("verbatim_quote"),
        "source_url": result_dict.get("source_url"),
        "checked_date": str(date.today()),
    }
    mask = df["program_name"].str.strip().str.lower() == program_name.strip().lower()
    if mask.any():
        df = df[~mask]
    st.session_state["results"] = pd.concat([df, pd.DataFrame([row])], ignore_index=True)


def load_from_uploaded(file) -> int:
    try:
        uploaded = pd.read_csv(file)
        for col in _COLUMNS:
            if col not in uploaded.columns:
                uploaded[col] = None
        uploaded = uploaded[_COLUMNS]
        existing = st.session_state["results"]
        combined = pd.concat([existing, uploaded], ignore_index=True)
        combined["checked_date"] = pd.to_datetime(combined["checked_date"], errors="coerce")
        combined = combined.sort_values("checked_date", ascending=False)
        combined = combined.drop_duplicates(subset=["program_name"], keep="first")
        combined["checked_date"] = combined["checked_date"].dt.date.astype(str)
        st.session_state["results"] = combined.reset_index(drop=True)
        return len(uploaded)
    except Exception:
        return 0


def to_csv_bytes() -> bytes:
    df: pd.DataFrame = st.session_state["results"]
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
