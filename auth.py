import os

import streamlit as st


def show_login_gate() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.title("Residency Signal Checker")
    st.markdown("---")
    with st.form("login_form"):
        passphrase = st.text_input("Enter passphrase", type="password")
        submitted = st.form_submit_button("Enter")

    if submitted:
        expected = st.secrets.get("ACCESS_PASSPHRASE") or os.environ.get("ACCESS_PASSPHRASE", "")
        if passphrase == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect passphrase.")

    return False
