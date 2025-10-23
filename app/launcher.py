# Project Aegis - 앱 런처
# 사용자가 원하는 앱을 선택할 수 있는 메인 런처
# 작성일: 2025.09.29

# --- add project root to sys.path ---
import os, sys
import importlib.util
import site

# .env 파일 로드
try:
    from dotenv import load_dotenv
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    load_dotenv(os.path.join(ROOT, '.env'))
except ImportError:
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Streamlit 환경에서 site-packages 경로 추가
for site_dir in site.getsitepackages():
    if site_dir not in sys.path:
        sys.path.insert(0, site_dir)
if site.ENABLE_USER_SITE and site.USER_SITE not in sys.path:
    sys.path.insert(0, site.USER_SITE)
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

# 데모 테넌트일 경우 환경변수를 조기에 설정 (import 이전)
# auth_ui.py가 SUPABASE_URL/KEY를 import할 때 올바른 값을 읽도록 함
if TENANT_ID == 'demo':
    try:
        from app.config_supabase import SUPABASE_DEMO_URL, SUPABASE_DEMO_KEY
        if SUPABASE_DEMO_URL and SUPABASE_DEMO_KEY:
            os.environ['SUPABASE_URL'] = SUPABASE_DEMO_URL
            os.environ['SUPABASE_KEY'] = SUPABASE_DEMO_KEY
            print(f"[INFO] Demo tenant Supabase configured early: {SUPABASE_DEMO_URL}")
    except Exception as e:
        print(f"[WARNING] Failed to set demo Supabase early: {e}")

# tenant_id에서 회사명 매핑 (한글 인코딩 문제 방지)
COMPANY_MAP = {
    'dooho': '두호',
    'kukje': '국제',
    'demo': 'Aegis-Demo (데모)',
}
COMPANY_NAME = COMPANY_MAP.get(TENANT_ID, TENANT_ID) if TENANT_ID else '회사 선택'

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
    # 데모 테넌트는 라이선스 체크 스킵
    if TENANT_ID != 'demo':
        try:
            from app.config_supabase import get_supabase_client
            from utils.license_manager import check_and_enforce_license

            supabase = get_supabase_client()
            check_and_enforce_license(supabase, TENANT_ID)
        except ImportError:
            # 라이선스 관리자가 없으면 경고만 표시
            print("[WARNING] License manager not found - skipping license check")
        except Exception as e:
            print(f"[WARNING] License check failed: {e}")
    else:
        # 데모 테넌트 실행 알림
        from app.config_supabase import SUPABASE_DEMO_URL, SUPABASE_DEMO_KEY

        if not SUPABASE_DEMO_URL or not SUPABASE_DEMO_KEY:
            st.warning("⚠️ 데모 모드 구성 진행 중")
            st.info("""
            **데모 Supabase 설정이 필요합니다.**

            다음 환경변수를 설정한 후 앱을 다시 시작하세요:
            - SUPABASE_DEMO_URL: Aegis-Demo Supabase 프로젝트 URL
            - SUPABASE_DEMO_KEY: Aegis-Demo Supabase API 키

            현재 기본 테넌트 Supabase로 임시 연결합니다.
            """)
        else:
            st.info("🎯 데모 모드로 실행 중입니다.")


    # 사이드바에서 앱 선택
    with st.sidebar:
        st.header("📱 앱 선택")

        selected_app = st.radio(
            "앱 목록",
            [
                "🏠 홈",
                "📊 PTOP 업무자동화",
                "🏗️ WIP 현황관리",
            ],
            key="app_selector"
        )

        st.markdown("---")
 
    # 선택된 앱에 따라 실행
    if selected_app == "🏠 홈":
        render_home_page()
    elif selected_app == "📊 PTOP 업무자동화":
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
        tab1, tab2 = st.tabs(["📊 PTOP 업무자동화", "🏗️ WIP 현황 관리"])
        
        with tab1:
            st.markdown("""
            #### 📊 PTOP(Process To Pay) 자동화 시스템
            
            **주요 기능:**
            - 📋 **자재내역서 생성**: 모델별 BOM 기반 자동 산출 및 Excel 출력
            - 📃 **견적서 자동 작성**: 템플릿 기반 전문 견적서 자동 생성
            - 📦 **발주서 작성**: 카테고리별 발주서 분리 생성
            - ✏️ **BOM 편집**: 인라인 편집으로 실시간 BOM 관리
            """)
           
        
        with tab2:
            st.markdown("""
            #### 🏗️ WIP(Work-In-Process) 현황 관리
            
            **주요 기능:**
            - 📊 **실시간 대시보드**: 진행 중, 지연, 완료 건수 한눈에 파악
            - 🔄 **공정 추적**: Cut → Bend → Laser → Paint → QA → Receive 단계별 진행률
            - 📈 **통계**: 기간별 매출 확인
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
        #### 📊 PTOP 업무자동화 시작하기
        1. 좌측 메뉴에서 "📊 PTOP 업무자동화" 선택
        2. 모델 검색으로 필요한 제품 찾기
        3. 자재내역서 생성으로 BOM 확인
        4. 발주서 자동 생성
        5. 견적서만 필요한 경우 견적서 작성
        6. BOM 편집기로 자재내역 수정      
        """)
    
    with col2:
        st.markdown("""
        #### 🏗️ WIP 현황 관리 시작하기
        1. 좌측 메뉴에서 "🏗️ WIP 현황 관리" 선택
        2. 대시보드에서 선택 후 
        3. 프로젝트 요약 탭에서 프로젝트 생성 및 정보 입력
        4. 발주상세 탭에서 진행 상황 확 업데이트
        """)

def render_main_app():
    """통합 PTOP 앱 실행 - ptop_app_v092.py 호출 (mode="pilot")"""
    try:
        # 환경변수 리셋 (demo가 아닌 경우)
        # ptop_app_v091.py에서 읽을 기본 Supabase 설정 복구
        if TENANT_ID != 'demo':
            from app.config_supabase import SUPABASE_URL, SUPABASE_KEY
            os.environ['SUPABASE_URL'] = SUPABASE_URL
            os.environ['SUPABASE_KEY'] = SUPABASE_KEY

        app_filename = "ptop_app_v092.py"
        print(f"[INFO] Loading unified PTOP app: {app_filename} (mode=pilot) for tenant: {TENANT_ID}")

        # app/ 폴더의 파일만 정확하게 찾기
        main_app_path = os.path.join(current_dir, app_filename)

        if not os.path.exists(main_app_path):
            st.error(f"""
            ❌ **PTOP 통합 앱 파일을 찾을 수 없습니다.**

            **찾으려는 파일:** {app_filename}
            **기대 경로:** {main_app_path}
            **회사:** {COMPANY_NAME} (tenant_id: {TENANT_ID})

            **해결 방법:**
            1. `{app_filename}` 파일이 `app/` 폴더에 있는지 확인
            2. 파일 이름 확인
            """)
            return

        # 동적 임포트 (작업 디렉토리는 변경하지 않음!)
        spec = importlib.util.spec_from_file_location("ptop_app_v092", main_app_path)
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
    """WIP 앱 v092 실행 - 사용자 권한 기반"""
    try:
        # 환경변수 리셋 (demo가 아닌 경우)
        if TENANT_ID != 'demo':
            from app.config_supabase import SUPABASE_URL, SUPABASE_KEY
            os.environ['SUPABASE_URL'] = SUPABASE_URL
            os.environ['SUPABASE_KEY'] = SUPABASE_KEY

        user = get_current_user()
        if not user:
            st.warning("WIP 앱을 보려면 로그인이 필요합니다.")
            return

        # auth_manager를 통해 사용자가 접근할 수 있는 테넌트 목록 가져오기
        from app.config_supabase import get_auth_manager
        auth_manager = get_auth_manager()
        allowed_tenants = auth_manager.get_allowed_tenants(user['email'])

        # Demo 테넌트는 항상 접근 가능하도록 추가 (데모 계정 demo@demo.com의 경우)
        if user['email'] == 'demo@demo.com':
            if not allowed_tenants:
                allowed_tenants = []
            if 'demo' not in allowed_tenants:
                allowed_tenants.append('demo')
            st.info("🎯 데모 모드로 WIP 앱에 접근합니다.")

        if not allowed_tenants:
            st.error("접근 가능한 업체 정보가 없습니다. 관리자에게 문의하세요.")
            return

        print(f"[INFO] Loading WIP app v092 for user: {user['email']} with tenants: {allowed_tenants}")

        # 1단계: app/ 폴더의 파일만 정확하게 찾기
        app_filename = "wip_app_v092.py"
        wip_app_path = os.path.join(current_dir, app_filename)

        if not os.path.exists(wip_app_path):
            st.error(f"❌ **WIP 앱({app_filename})을 찾을 수 없습니다!**")
            st.write(f"**기대 경로:** {wip_app_path}")
            return

        # 2단계: 임포트
        spec = importlib.util.spec_from_file_location("wip_app_v092", wip_app_path)
        wip_app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wip_app_module)

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
