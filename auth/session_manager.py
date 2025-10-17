# /auth/session_manager.py
import streamlit as st

def get_current_user():
    return st.session_state.get("auth_user")

def require_login():
    if not get_current_user():
        st.stop()

def set_user_profile(profile: dict):
    st.session_state["user_profile"] = profile

def get_user_profile():
    return st.session_state.get("user_profile")

def logout_button(label="로그아웃", key: str = "logout"):
    if st.button(label, key=key, use_container_width=False):
        for k in ["auth_user", "auth_token", "user_profile"]:
            st.session_state.pop(k, None)
        st.rerun()
