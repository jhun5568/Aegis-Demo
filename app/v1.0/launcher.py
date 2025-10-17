# Project Aegis - 앱 런처
# 사용자가 원하는 앱을 선택할 수 있는 메인 런처
# 작성일: 2025.09.29

import streamlit as st
import sys
import os

# 작업 디렉토리를 스크립트 위치로 강제 변경
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)  # 이 줄이 핵심!

parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)
sys.path.append(parent_dir)

print(f"[DEBUG] 작업 디렉토리를 {current_dir}로 변경했습니다.")
print(f"[DEBUG] 현재 작업 디렉토리: {os.getcwd()}")
print(f"[DEBUG] 스크립트 위치: {current_dir}")
print(f"[DEBUG] 부모 디렉토리: {parent_dir}")

# 페이지 설정
st.set_page_config(
    page_title="Project Aegis - 업무자동화 시스템",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """메인 런처 함수"""
    
    # 헤더
    st.title("🚀 Project Aegis")
    st.markdown("### 업무자동화 시스템 런처")
    st.markdown("---")
    
    # 사이드바에서 앱 선택
    with st.sidebar:
        st.header("📱 앱 선택")
        st.markdown("사용하실 기능을 선택해주세요.")
        
        selected_app = st.radio(
            "앱 목록",
            [
                "🏠 홈 (앱 소개)",
                "📊 견적/발주 자동화 (기존)",
                "🏗️ WIP 현황 관리 (신규)",
            ],
            key="app_selector"
        )
        
        st.markdown("---")
        st.info("💡 **팁**: 각 앱은 독립적으로 동작하며, 동일한 데이터베이스를 공유합니다.")
    
    # 선택된 앱에 따라 실행
    if selected_app == "🏠 홈 (앱 소개)":
        render_home_page()
    elif selected_app == "📊 견적/발주 자동화 (기존)":
        render_main_app()
    elif selected_app == "🏗️ WIP 현황 관리 (신규)":
        render_wip_app()

def render_home_page():
    """홈 페이지 렌더링"""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("👋 Project Aegis에 오신 것을 환영합니다!")
        
        st.markdown("""
        **Project Aegis**는 금속 구조물 제작 업무를 자동화하는 통합 솔루션입니다.
        
        20년간의 현장 경험과 AI 협업으로 개발된 실용적인 도구로, 
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
        st.markdown("### 📈 시스템 현황")
        
        # 더미 통계 (실제로는 데이터베이스에서 가져와야 함)
        st.metric("전체 모델", "1,200+", "개")
        st.metric("등록된 자재", "2,400+", "개") 
        st.metric("활성 프로젝트", "45", "건")
        
        st.markdown("---")
        
        st.markdown("### 🔧 시스템 요구사항")
        st.markdown("""
        - **Python 3.8+**
        - **Streamlit**
        - **pandas, openpyxl**
        - **Excel 파일 지원**
        """)
        
        st.markdown("---")
        
        st.markdown("### 📞 지원")
        st.info("""
        **개발자**: 배성준 (Aegis_BIMer)
        
        **문의사항**이 있으시면 언제든지 연락주세요.
        """)
    
    # 빠른 시작 가이드
    st.markdown("---")
    st.header("🚀 빠른 시작")
    
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
    """기존 메인 앱 실행"""
    try:
        # 여러 가능한 경로에서 파일 찾기
        possible_paths = [
            os.path.join(current_dir, "main_app.py"),           # 가장 우선순위
            os.path.join(current_dir, "dooho_quotation_app_v0.85.py"),
            os.path.join(parent_dir, "main_app.py"),
            "main_app.py",  # 현재 작업 디렉토리
            "dooho_quotation_app_v0.85.py"
        ]
        
        main_app_path = None
        for path in possible_paths:
            if os.path.exists(path):
                main_app_path = path
                break
        
        if not main_app_path:
            st.error(f"""
            ❌ **기존 앱 파일을 찾을 수 없습니다.**
            
            **찾은 경로들:**
            """)
            for path in possible_paths:
                exists = "✅ 존재" if os.path.exists(path) else "❌ 없음"
                st.write(f"- {path} : {exists}")
            
            st.info("""
            **해결 방법:**
            1. 터미널에서 `cd app` 명령으로 app 폴더로 이동
            2. `streamlit run launcher.py` 실행
            3. 또는 `dooho_quotation_app_v0.85.py` 파일을 같은 폴더에 복사
            """)
            return
        print(f"[DEBUG] 기존 앱 파일 찾음: {main_app_path}")
        
        # 동적 임포트
        import importlib.util
        spec = importlib.util.spec_from_file_location("main_app", main_app_path)
        main_app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_app_module)
        
        # 메인 함수 실행
        if hasattr(main_app_module, 'main'):
            main_app_module.main()
        else:
            st.error("❌ main() 함수를 찾을 수 없습니다.")
            
    except Exception as e:
        st.error(f"""
        ❌ **기존 앱 로딩 중 오류 발생**
        
        **오류 내용**: {str(e)}
        
        **해결 방법**:
        1. `dooho_quotation_app_v0.85.py` 파일이 `app/` 폴더에 있는지 확인
        2. 파일 이름을 `main_app.py`로 변경하거나
        3. 위 코드의 경로를 실제 파일명에 맞게 수정
        """)

# Project Aegis - 앱 런처
# 사용자가 원하는 앱을 선택할 수 있는 메인 런처
# 작성일: 2025.09.29

import streamlit as st
import sys
import os

# 작업 디렉토리를 스크립트 위치로 강제 변경
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)  # 이 줄이 핵심!

parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)
sys.path.append(parent_dir)

print(f"[DEBUG] 작업 디렉토리를 {current_dir}로 변경했습니다.")
print(f"[DEBUG] 현재 작업 디렉토리: {os.getcwd()}")
print(f"[DEBUG] 스크립트 위치: {current_dir}")
print(f"[DEBUG] 부모 디렉토리: {parent_dir}")

# 페이지 설정
st.set_page_config(
    page_title="Project Aegis - 업무자동화 시스템",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """메인 런처 함수"""
    
    # 헤더
    st.title("🚀 Project Aegis")
    st.markdown("### 업무자동화 시스템 런처")
    st.markdown("---")
    
    # 사이드바에서 앱 선택
    with st.sidebar:
        st.header("📱 앱 선택")
        st.markdown("사용하실 기능을 선택해주세요.")
        
        selected_app = st.radio(
            "앱 목록",
            [
                "🏠 홈 (앱 소개)",
                "📊 견적/발주 자동화 (기존)",
                "🏗️ WIP 현황 관리 (신규)",
            ],
            key="app_selector"
        )
        
        st.markdown("---")
        st.info("💡 **팁**: 각 앱은 독립적으로 동작하며, 동일한 데이터베이스를 공유합니다.")
    
    # 선택된 앱에 따라 실행
    if selected_app == "🏠 홈 (앱 소개)":
        render_home_page()
    elif selected_app == "📊 견적/발주 자동화 (기존)":
        render_main_app()
    elif selected_app == "🏗️ WIP 현황 관리 (신규)":
        render_wip_app()

def render_home_page():
    """홈 페이지 렌더링"""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("👋 Project Aegis에 오신 것을 환영합니다!")
        
        st.markdown("""
        **Project Aegis**는 금속 구조물 제작 업무를 자동화하는 통합 솔루션입니다.
        
        20년간의 현장 경험과 AI 협업으로 개발된 실용적인 도구로, 
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
        st.markdown("### 📈 시스템 현황")
        
        # 더미 통계 (실제로는 데이터베이스에서 가져와야 함)
        st.metric("전체 모델", "1,200+", "개")
        st.metric("등록된 자재", "2,400+", "개") 
        st.metric("활성 프로젝트", "45", "건")
        
        st.markdown("---")
        
        st.markdown("### 🔧 시스템 요구사항")
        st.markdown("""
        - **Python 3.8+**
        - **Streamlit**
        - **pandas, openpyxl**
        - **Excel 파일 지원**
        """)
        
        st.markdown("---")
        
        st.markdown("### 📞 지원")
        st.info("""
        **개발자**: 배성준 (Aegis_BIMer)
        
        **문의사항**이 있으시면 언제든지 연락주세요.
        """)
    
    # 빠른 시작 가이드
    st.markdown("---")
    st.header("🚀 빠른 시작")
    
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
    """기존 메인 앱 실행"""
    try:
        # 여러 가능한 경로에서 파일 찾기
        possible_paths = [
            os.path.join(current_dir, "main_app.py"),           # 가장 우선순위
            os.path.join(current_dir, "dooho_quotation_app_v0.85.py"),
            os.path.join(parent_dir, "main_app.py"),
            "main_app.py",  # 현재 작업 디렉토리
            "dooho_quotation_app_v0.85.py"
        ]
        
        main_app_path = None
        for path in possible_paths:
            if os.path.exists(path):
                main_app_path = path
                break
        
        if not main_app_path:
            st.error(f"""
            ❌ **기존 앱 파일을 찾을 수 없습니다.**
            
            **찾은 경로들:**
            """)
            for path in possible_paths:
                exists = "✅ 존재" if os.path.exists(path) else "❌ 없음"
                st.write(f"- {path} : {exists}")
            
            st.info("""
            **해결 방법:**
            1. 터미널에서 `cd app` 명령으로 app 폴더로 이동
            2. `streamlit run launcher.py` 실행
            3. 또는 `dooho_quotation_app_v0.85.py` 파일을 같은 폴더에 복사
            """)
            return
        print(f"[DEBUG] 기존 앱 파일 찾음: {main_app_path}")
        
        # 동적 임포트
        import importlib.util
        spec = importlib.util.spec_from_file_location("main_app", main_app_path)
        main_app_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_app_module)
        
        # 메인 함수 실행
        if hasattr(main_app_module, 'main'):
            main_app_module.main()
        else:
            st.error("❌ main() 함수를 찾을 수 없습니다.")
            
    except Exception as e:
        st.error(f"""
        ❌ **기존 앱 로딩 중 오류 발생**
        
        **오류 내용**: {str(e)}
        
        **해결 방법**:
        1. `dooho_quotation_app_v0.85.py` 파일이 `app/` 폴더에 있는지 확인
        2. 파일 이름을 `main_app.py`로 변경하거나
        3. 위 코드의 경로를 실제 파일명에 맞게 수정
        """)

def render_wip_app():
    """WIP 앱 실행 - 수정본"""
    try:
        # WIP 앱 임포트
        from wip_app import WIPManager
        
        # 디버깅 정보
        import sys
        st.sidebar.info(f"Python 버전: {sys.version_info.major}.{sys.version_info.minor}")
        
        # WIP 매니저 초기화 및 실행
        wip_manager = WIPManager()
        wip_manager.render_wip_dashboard()
        
    except ImportError as e:
        st.error(f"""
        ❌ **WIP 앱을 찾을 수 없습니다.**
        
        **오류**: {str(e)}
        
        **해결 방법**:
        1. `wip_app.py` 파일이 같은 폴더에 있는지 확인
        2. 파일 내용이 올바르게 저장되었는지 확인
        3. Python 경로 설정 확인
        """)
        import traceback
        st.code(traceback.format_exc())
        
    except AttributeError as e:
        st.error(f"""
        ❌ **WIP 앱 초기화 중 오류 발생**
        
        **오류 내용**: {str(e)}
        
        **가능한 원인**:
        - wip_app.py 파일이 완전히 저장되지 않았을 수 있습니다
        - Part 1~4 코드가 모두 제대로 붙여넣어졌는지 확인하세요
        
        **해결 방법**:
        1. wip_app.py 파일을 다시 확인
        2. 모든 클래스와 함수가 올바르게 정의되었는지 확인
        """)
        import traceback
        st.code(traceback.format_exc())
        
    except Exception as e:
        st.error(f"""
        ❌ **WIP 앱 실행 중 오류 발생**
        
        **오류 타입**: {type(e).__name__}
        **오류 내용**: {str(e)}
        
        **디버깅 정보가 아래에 표시됩니다.**
        """)
        
        # 상세 트레이스백 표시
        import traceback
        st.code(traceback.format_exc())
        
        # 오류 발생 위치 힌트
        if "'dict' object has no attribute 'empty'" in str(e):
            st.warning("""
            💡 **이 오류는 다음 중 하나입니다:**
            
            1. `get_all_orders()` 함수가 DataFrame 대신 dict를 반환
            2. `get_statistics()` 함수의 반환값 문제
            
            **즉시 해결 방법**: 
            - '백업/샘플' 탭으로 이동
            - '샘플 데이터 입력' 버튼 클릭
            """)

if __name__ == "__main__":
    main()
