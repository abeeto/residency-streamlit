import streamlit as st

import auth
import claude_agent
import results_store

st.set_page_config(page_title="Residency Signal Checker", page_icon="🏥", layout="centered")

if not auth.show_login_gate():
    st.stop()

results_store.init_store()


def render_result(result: dict, from_cache: bool = False):
    cache_note = f" *(cached — {result.get('checked_date', '')})*" if from_cache else ""

    if result.get("error"):
        st.warning(f"Could not parse a result.{cache_note}")
        with st.expander("Show raw response"):
            st.text(result.get("raw_response", ""))
        return

    signal = result.get("signal_required_explicit")
    if signal is True:
        st.markdown(
            f"<span style='background:#ff4b4b;color:white;padding:4px 12px;"
            f"border-radius:12px;font-weight:bold'>🔴 Signal Required</span>{cache_note}",
            unsafe_allow_html=True,
        )
        with st.expander("See exact quote and source"):
            quote = result.get("verbatim_quote") or ""
            url = result.get("source_url") or ""
            st.markdown(f"> {quote}")
            if url:
                st.markdown(f"[Source]({url})")
    else:
        st.markdown(
            f"<span style='background:#e0e0e0;color:#444;padding:4px 12px;"
            f"border-radius:12px;font-weight:bold'>⚪ Not Found</span>{cache_note}",
            unsafe_allow_html=True,
        )


# --- Sidebar ---
with st.sidebar:
    st.header("How to use")
    st.markdown(
        "Type one or more program names and click **Check Programs**. "
        "The app searches each program's official website for an explicit statement "
        "that a signal is required to receive an interview.\n\n"
        "Results stay for this session. Download before closing, "
        "and upload next time to pick up where you left off."
    )
    st.divider()

    uploaded = st.file_uploader("Restore previous results (upload CSV)", type="csv", key="csv_upload")
    if uploaded:
        n = results_store.load_from_uploaded(uploaded)
        st.success(f"Loaded {n} programs from file.")

    df = st.session_state.get("results")
    has_results = df is not None and not df.empty
    st.download_button(
        "Download my results (CSV)",
        data=results_store.to_csv_bytes(),
        file_name="residency_signal_results.csv",
        mime="text/csv",
        disabled=not has_results,
    )

    st.divider()
    if st.button("Log out"):
        st.session_state["authenticated"] = False
        st.rerun()


# --- Main ---
st.title("🏥 Residency Signal Checker")

program_input = st.text_area(
    "Enter program names, one per line",
    placeholder="Mayo Clinic Internal Medicine\nMGH Psychiatry\nUCLA Emergency Medicine",
    height=150,
)

check_clicked = st.button("Check Programs", type="primary", disabled=not program_input.strip())

if check_clicked:
    programs = [p.strip() for p in program_input.splitlines() if p.strip()]

    for program in programs:
        st.markdown(f"### {program}")
        cached = results_store.find_cached(program)

        if cached and cached.get("signal_required_explicit") is not None:
            render_result(cached, from_cache=True)
            st.divider()
            continue

        stream_placeholder = st.empty()

        def make_callback(placeholder):
            def callback(text):
                placeholder.markdown(
                    f"<div style='font-size:0.85em;color:#666;"
                    f"white-space:pre-wrap;max-height:200px;overflow-y:auto'>{text}</div>",
                    unsafe_allow_html=True,
                )
            return callback

        try:
            result = claude_agent.check_program(program, stream_callback=make_callback(stream_placeholder))
        except Exception as e:
            stream_placeholder.empty()
            st.error(f"Error checking {program}: {e}")
            st.divider()
            continue

        stream_placeholder.empty()
        results_store.save_result(result)
        render_result(result)
        st.divider()


# --- History table ---
df = st.session_state.get("results")
if df is not None and not df.empty:
    st.subheader("All checked programs this session")
    display_df = df[["program_name", "signal_required_explicit", "checked_date"]].copy()
    display_df["signal_required_explicit"] = display_df["signal_required_explicit"].map(
        {True: "✅ Signal Required", False: "⚪ Not Found", None: "⚠️ Error"}
    )
    display_df.columns = ["Program", "Result", "Date Checked"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
