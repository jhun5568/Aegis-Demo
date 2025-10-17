# Project Aegis - 앱 런처
# 사용자가 원하는 앱을 선택할 수 있는 메인 런처
# 작성일: 2025.09.29

# --- add project root to sys.path ---
import os, sys
import importlib.util
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# ------------------------------------

# launcher.py (발췌)
import streamlit as st
from auth.session_manager import get_current_user, logout_button
from auth.auth_ui import render_auth_gate, topbar_user

# 환경변수 또는 URL 파라미터에서 회사 정보 읽기
# URL 파라미터 우선 (Streamlit Cloud용), 없으면 환경변수 (로컬용)
try:
    url_tenant = st.query_params.get("tenant", None)
    TENANT_ID = url_tenant if url_tenant else os.getenv('TENANT_ID', 'dooho')
except:
    TENANT_ID = os.getenv('TENANT_ID', 'dooho')  # 기본값: dooho

# tenant_id에서 회사명 매핑 (한글 인코딩 문제 방지)
COMPANY_MAP = {
    'dooho': '두호',
    'kukje': '국제',
}
COMPANY_NAME = COMPANY_MAP.get(TENANT_ID, TENANT_ID)

st.set_page_config(
    page_title=f"{COMPANY_NAME} 자동화 시스템",
    page_icon="🛠️",
    layout="wide"
)

# 경로 설정 (작업 디렉토리는 변경하지 않음)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# sys.path에만 추가
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

print(f"[DEBUG] 스크립트 위치: {current_dir}")
print(f"[DEBUG] 부모 디렉토리: {parent_dir}")
print(f"[DEBUG] 현재 작업 디렉토리: {os.getcwd()}")

def main():
    """메인 런처 함수"""
    topbar_user()
    user = get_current_user()

    # 회사명 표시
    st.subheader(f"🏢 {COMPANY_NAME} 자동화 시스템")

    if not user:
        st.info("이용을 위해 로그인이 필요합니다.")
        render_auth_gate()
        st.stop()
    else:
        logout_button(key="logout_main")

    # 라이선스 체크 (로그인 후)
    try:
        from app.config_supabase import get_supabase_client
        from utils.license_manager import check_and_enforce_license

        # 라이선스 체크는 테넌트별 1회만 수행
        _lic_key = f"license_checked::{TENANT_ID}"
        if _lic_key not in st.session_state:
            try:
                supabase = get_supabase_client()
                check_and_enforce_license(supabase, TENANT_ID)
            except Exception as license_error:
                st.warning(f"⚠️ 라이선스 서버에 일시적인 문제가 발생했습니다. 기능은 정상적으로 사용 가능합니다.")
                print(f"[EMERGENCY] License check bypassed due to error: {license_error}")
            finally:
                # 성공하든 실패하든 다시 체크하지 않도록 세션 상태 설정
                st.session_state[_lic_key] = True
    except ImportError:
        # 라이선스 관리자가 없으면 경고만 표시
        print("[WARNING] License manager not found - skipping license check")
    except Exception as e:
        print(f"[WARNING] License check failed: {e}")


    # 사이드바에서 앱 선택
    with st.sidebar:
        st.header("📱 앱 선택")

        selected_app = st.radio(
            "앱 목록",
            [
                "🏠 홈",
                "📊 견적/발주 자동화",
                "🏗️ WIP 현황관리",
            ],
            key="app_selector"
        )

        st.markdown("---")
 
    # 선택된 앱에 따라 실행
    if selected_app == "🏠 홈":
        render_home_page()
    elif selected_app == "📊 견적/발주 자동화":
        render_main_app()
    elif selected_app == "🏗️ WIP 현황관리":
        render_wip_app()

def render_home_page():
    """홈 페이지 렌더링"""
    
    col1, col2 = st.columns([10, 3])
    
    with col1:
        st.markdown("""
        금속 구조물 제작 업무를 자동화하는 통합 솔루션입니다.
                   
        복잡한 견적, 발주, 진행 관리 업무를 간소화합니다.
        """)
        
        st.markdown("### 🛠️ 제공 기능")
        
        # 기능 소개 카드
        tab1, tab2 = st.tabs(["📊 견적/발주 자동화", "🏗️ WIP 현황 관리"])
        
        with tab1:
            st.markdown("""
            #### 📊 견적/발주 자동화 시스템
            
            **주요 기능:**
            - 🔍 **모델 검색**: 다중 컬럼 검색으로 원하는 모델 빠르게 찾기
            - 📋 **자재내역서 생성**: BOM 기반 자동 산출 및 Excel 출력
            - 📃 **견적서 작성**: 템플릿 기반 전문 견적서 자동 생성
            - 📦 **발주서 작성**: 카테고리별 발주서 분리 생성
            - ✏️ **BOM 편집**: 인라인 편집으로 실시간 BOM 관리
            
            **적용 분야:**
            - 휀스, 자전거 보관대, 볼라드, 차양 등 금속 구조물 제작
            - 관급/사급 프로젝트 견적 및 발주 관리
            """)
        
        with tab2:
            st.markdown("""
            #### 🏗️ WIP(Work-In-Process) 현황 관리
            
            **주요 기능:**
            - 📊 **실시간 대시보드**: 진행 중, 지연, 완료 건수 한눈에 파악
            - 🔄 **공정 추적**: Cut → Bend → Laser → Paint → QA → Receive 단계별 진행률
            - 📅 **일정 관리**: 납기일 기준 지연 경고 및 우선순위 표시
            - 📝 **진행 업데이트**: 실시간 작업 상태 입력 및 이력 관리
            - 🔍 **필터링**: 프로젝트/업체/상태별 맞춤 조회
            
            **해결 과제:**
            - 여러 외주업체에 분산된 가공 작업의 진행 상황 파악
            - 경영진과 현장 간의 정보 투명성 확보
            - 데이터 기반 의사결정 지원
            """)
    
    with col2:
     
        st.markdown("---")
        
        st.markdown("### 📞 지원")
        st.info("""
        **개발자**: Aegis_BIMer
        **문의**010-3812-7644
        """)
    
    # 빠른 시작 가이드
    st.markdown("---")
    st.subheader("🚀 빠른 시작")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        #### 📊 견적/발주 자동화 시작하기
        1. 좌측 메뉴에서 "📊 견적/발주 자동화" 선택
        2. 모델 검색으로 필요한 제품 찾기
        3. 자재내역서 생성으로 BOM 확인
        4. 견적서/발주서 자동 생성
        """)
    
    with col2:
        st.markdown("""
        #### 🏗️ WIP 현황 관리 시작하기
        1. 좌측 메뉴에서 "🏗️ WIP 현황 관리" 선택
        2. Orders 시트에 발주 정보 입력
        3. 대시보드에서 전체 현황 파악
        4. 개별 발주의 진행 상황 업데이트
        """)

def render_main_app():
    """통합 PTOP 앱 실행 - ptop_app_v091.py 호출 (mode="pilot")"""
    try:
        app_filename = "ptop_app_v091.py"
        print(f"[INFO] Loading unified PTOP app: {app_filename} (mode=pilot) for tenant: {TENANT_ID}")

        # 여러 가능한 경로에서 파일 찾기
        possible_paths = [
            os.path.join(current_dir, app_filename),
            os.path.join(parent_dir, "app", app_filename),
            app_filename
        ]

        main_app_path = None
        for path in possible_paths:
            if os.path.exists(path):
                main_app_path = os.path.abspath(path)
                break
        
        if not main_app_path:
            st.error(f"""
            ❌ **PTOP 통합 앱 파일을 찾을 수 없습니다.**

            **찾으려는 파일:** {app_filename}
            **회사:** {COMPANY_NAME} (tenant_id: {TENANT_ID})

            **해결 방법:**
            1. `{app_filename}` 파일이 `app/` 폴더에 있는지 확인
            2. 파일 이름 확인
            """)

            st.write("**확인한 경로들:**")
            for path in possible_paths:
                exists = "✅ 존재" if os.path.exists(path) else "❌ 없음"
                st.write(f"- {path} : {exists}")
            return
        
        print(f"[DEBUG] PTOP 통합 앱 파일 찾음: {main_app_path}")
        
        # 동적 임포트 (작업 디렉토리는 변경하지 않음!)
        spec = importlib.util.spec_from_file_location("ptop_app_v091", main_app_path)
        ptop_app_module = importlib.util.module_from_spec(spec)
        
        # sys.path에 앱 디렉토리 추가
        app_dir = os.path.dirname(main_app_path)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        spec.loader.exec_module(ptop_app_module)
        
        # 메인 함수 실행 (mode="pilot" 파라미터 전달)
        if hasattr(ptop_app_module, 'main'):
            with st.spinner(f"Loading {COMPANY_NAME} quotation automation app..."):
                ptop_app_module.main(mode="pilot")
        else:
            st.error("❌ main() 함수를 찾을 수 없습니다.")
            
    except Exception as e:
        st.error(f"""
        ❌ **PTOP 통합 앱 로딩 중 오류 발생**
        
        **오류 타입**: {type(e).__name__}
        **오류 내용**: {str(e)}
        """)
        
        import traceback
        st.code(traceback.format_exc())

def render_wip_app():
    """WIP 앱 v0.9 실행 - 사용자 권한 기반"""
    try:
        user = get_current_user()
        if not user:
            st.warning("WIP 앱을 보려면 로그인이 필요합니다.")
            return

        # auth_manager를 통해 사용자가 접근할 수 있는 테넌트 목록 가져오기
        from app.config_supabase import get_auth_manager
        auth_manager = get_auth_manager()
        # 사용자별 허용 테넌트 목록은 세션 캐시
        _ak = f"allowed_tenants::{user['email']}"
        if _ak not in st.session_state:
            st.session_state[_ak] = auth_manager.get_allowed_tenants(user['email'])
        allowed_tenants = st.session_state[_ak]

        if not allowed_tenants:
            st.error("접근 가능한 업체 정보가 없습니다. 관리자에게 문의하세요.")
            return

        print(f"[INFO] Loading WIP app v0.9 for user: {user['email']} with tenants: {allowed_tenants}")

        # 1단계: 경로 찾기
        app_filename = "wip_app_v0.9.py"
        possible_paths = [
            os.path.join(current_dir, app_filename),
            os.path.join(parent_dir, "app", app_filename),
            app_filename
        ]

        wip_app_path = None
        for path in possible_paths:
            if os.path.exists(path):
                wip_app_path = path
                break

        if not wip_app_path:
            st.error(f"❌ **WIP 앱({app_filename})을 찾을 수 없습니다!**")
            return

        # 2단계: 임포트 (세션 캐시)
        if (
            'wip_app_module' not in st.session_state
            or st.session_state.get('wip_app_path') != wip_app_path
        ):
            spec = importlib.util.spec_from_file_location("wip_app_v0_9", wip_app_path)
            wip_app_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wip_app_module)
            st.session_state['wip_app_module'] = wip_app_module
            st.session_state['wip_app_path'] = wip_app_path
        else:
            wip_app_module = st.session_state['wip_app_module']

        # 3단계: main 함수 확인 및 allowed_tenants 전달
        if hasattr(wip_app_module, 'main'):
            with st.spinner(f"Loading WIP dashboard..."):
                wip_app_module.main(allowed_tenants=allowed_tenants)
        else:
            st.error("❌ main() 함수가 없습니다!")

    except Exception as e:
        st.error(f"❌ WIP 앱 로딩 중 오류 발생!")
        st.write(f"**오류 타입**: {type(e).__name__}")
        st.write(f"**오류 메시지**: {str(e)}")

        import traceback
        st.code(traceback.format_exc())

# 앱 실행
if __name__ == "__main__":
    main()
