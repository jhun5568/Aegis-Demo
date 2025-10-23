# /auth/auth_ui.py
import streamlit as st
from auth.auth_manager import AuthManager
from auth.storage_helper import load_auth_token

# --- Secrets에서 Supabase 설정 읽기 ---
# .streamlit/secrets.toml 내 [supabase] 섹션을 사용합니다.
try:
    SUPABASE_URL = st.secrets["supabase"]["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["supabase"]["SUPABASE_KEY"]
except Exception:
    try:
        from app.config_supabase import SUPABASE_URL as SUPABASE_URL, SUPABASE_KEY as SUPABASE_KEY
    except Exception:
        import os as _os
        SUPABASE_URL = _os.getenv("SUPABASE_URL")
        SUPABASE_KEY = _os.getenv("SUPABASE_KEY") or _os.getenv("SUPABASE_ANON_KEY")

def render_login(am: AuthManager):
    st.header("Project Aegis 로그인")
    with st.form("login_form"):
        email = st.text_input("이메일")
        pw    = st.text_input("비밀번호", type="password")
        remember_me = st.checkbox("🔒 자동 로그인 (30일간 유지)", value=True)
        submitted = st.form_submit_button("로그인")
    if submitted:
        ok, msg = am.sign_in(email, pw, remember_me=remember_me)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("회원가입"):
            st.session_state["auth_page"] = "signup"
            st.rerun()
    with col2:
        if st.button("비밀번호 재설정"):
            st.session_state["auth_page"] = "reset"
            st.rerun()

def render_signup(am: AuthManager):
    st.header("새 계정 만들기")
    with st.form("signup_form"):
        name  = st.text_input("이름")
        email = st.text_input("이메일")
        pw1   = st.text_input("비밀번호", type="password")
        pw2   = st.text_input("비밀번호 확인", type="password")
        submitted = st.form_submit_button("계정 만들기")
    if submitted:
        if pw1 != pw2:
            st.error("비밀번호가 일치하지 않습니다.")
        else:
            ok, msg = am.sign_up(email, pw1, name)
            if ok:
                st.success(msg)
                st.session_state["auth_page"] = "login"
            else:
                st.error(msg)

def render_reset(am: AuthManager):
    st.header("비밀번호 재설정")
    with st.form("reset_form"):
        email = st.text_input("이메일")
        submitted = st.form_submit_button("재설정 링크 보내기")
    if submitted:
        ok, msg = am.reset_password(email)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

def render_auth_gate():
    """런처에서 호출하는 인증 게이트(로그인/회원가입/재설정 라우팅)"""
    # 현재 환경변수에서 Supabase 설정 읽기 (데모 테넌트용 동적 설정 지원)
    import os as _os
    current_url = _os.getenv("SUPABASE_URL") or SUPABASE_URL
    current_key = _os.getenv("SUPABASE_KEY") or SUPABASE_KEY

    am = AuthManager(current_url, current_key)

    # 자동 로그인 시도 (파일에 저장된 토큰이 있으면)
    if "auth_user" not in st.session_state and "auto_login_attempted" not in st.session_state:
        st.session_state["auto_login_attempted"] = True  # 한 번만 시도

        saved_token = load_auth_token()
        if saved_token:
            token, email = saved_token
            with st.spinner(f"🔄 {email}(으)로 자동 로그인 중..."):
                ok, msg = am.sign_in_with_token(token)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    # 토큰 만료 시 자동으로 삭제됨 (load_auth_token에서 처리)
                    st.warning("자동 로그인이 만료되었습니다. 다시 로그인해주세요.")

    page = st.session_state.get("auth_page", "login")
    if page == "login":
        render_login(am)
    elif page == "signup":
        render_signup(am)
    else:
        render_reset(am)

def topbar_user():
    """우상단 사용자 표시(선택사항)"""
    user = st.session_state.get("auth_user")
    if user:
        st.markdown(
            f"<div style='text-align:right'>👤 {user.get('email','')}</div>",
            unsafe_allow_html=True
        )
