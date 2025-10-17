# WIP(Work-In-Process) 현황 관리 시스템 v0.7
# SQLite 기반 완전 재작성
# Project Aegis - 2025.10.08

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
import os
from contextlib import contextmanager
import time

# ✅ 데이터베이스 매니저 캐시 제거로 성능 개선
@st.cache_resource(show_spinner=False)
def get_db_manager():
    print("🚀 데이터베이스 매니저를 초기화합니다...")
    return DatabaseManager()

# 성능 모니터링 데코레이터만 유지
def monitor_performance(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        if execution_time > 5:
            print(f"⚠️ 느린 쿼리: {func.__name__} - {execution_time:.2f}초")
        elif execution_time > 2:
            print(f"ℹ️ 일반 쿼리: {func.__name__} - {execution_time:.2f}초")
        else:
            print(f"✅ 빠른 쿼리: {func.__name__} - {execution_time:.2f}초")
        
        return result
    return wrapper


# 🆕 Supabase 관련 import 추가
from config_supabase import (
    SUPABASE_URL, 
    SUPABASE_KEY, 
    USE_SUPABASE,
    PROCESS_STAGES
)

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ supabase-py 패키지가 설치되지 않았습니다.")

# ============================================================================
# 데이터베이스 유틸리티
# ============================================================================

# 페이지 설정 (launcher에서 실행 시 건너뜀)
if __name__ == "__main__":
    try:
        st.set_page_config(
            page_title="WIP 현황관리 v0.7",
            page_icon="🗂️",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    except:
        # launcher에서 실행 시 이미 설정되어 있음
        pass
    
# ============================================================================
# 데이터베이스 유틸리티
# ============================================================================

class DatabaseManager:
    """데이터베이스 관리 클래스 - SQLite/Supabase Hybrid"""
    
    def __init__(_self, db_path="wip_database.db"):
        """
        데이터베이스 초기화
        
        Args:
            db_path: SQLite DB 파일 경로
        """
        # 🆕 Supabase 모드 확인
        if USE_SUPABASE:
            if not SUPABASE_AVAILABLE:
                raise ImportError(
                    "Supabase를 사용하려면 supabase-py 패키지가 필요합니다.\n"
                    "설치: pip install supabase"
                )
            
            # Supabase 클라이언트 초기화
            _self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            print("✅ Supabase 모드로 실행 중")
        else:
            # SQLite 모드
            # 상대 경로가 주어진 경우 절대 경로로 변환
            if not os.path.isabs(db_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                _self.db_path = os.path.join(script_dir, db_path)
            else:
                _self.db_path = db_path
            
            print(f"🗄️ 데이터베이스 경로: {_self.db_path}")
            
            # 데이터베이스 초기화
            _self.initialize_database()
            print("✅ SQLite 모드로 실행 중")
            
    @contextmanager
    def get_connection(_self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = sqlite3.connect(_self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def initialize_database(_self):
        """데이터베이스 및 테이블 초기화 - v0.5 프로젝트 중심 구조"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 고객사 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    customer_id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    contact TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 1.5. 업체 마스터 테이블 (v0.5 신규)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    vendor_id TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    contact TEXT,
                    process_types TEXT,
                    memo TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. 프로젝트 테이블 (v2.1 완성 버전 + v0.5 계약금액 추가)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    customer_id TEXT,
                    final_due_date DATE NOT NULL,
                    contract_type TEXT DEFAULT '관급',
                    contract_amount INTEGER DEFAULT 0,
                    installation_completed_date DATE,
                    installation_staff_count INTEGER,
                    installation_days INTEGER,
                    tax_invoice_issued BOOLEAN DEFAULT 0,
                    trade_statement_issued BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT '진행중',
                    memo TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                )
            """)
            
            # 3. 발주 테이블 (project_id 추가)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    project_id TEXT,
                    project TEXT NOT NULL,
                    vendor TEXT NOT NULL,
                    order_date DATE,
                    due_date DATE,
                    status TEXT DEFAULT '진행중',
                    memo TEXT,
                    current_stage TEXT DEFAULT '미시작',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
                    FOREIGN KEY (project_id) REFERENCES projects(project_id)
                )
            """)
            
            # 4. 발주 품목 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    spec TEXT,
                    quantity TEXT DEFAULT '1식',
                    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
                )
            """)
                        
            # 5. 공정 진행 이벤트 테이블 (v2.0 - vendor 추가)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS process_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    planned_date DATE,
                    done_date DATE,
                    vendor TEXT,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'USER',
                    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
                )
            """)
            
            # 인덱스 생성
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_customer 
                ON orders(customer_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_project 
                ON orders(project_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_order 
                ON process_events(order_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_stage 
                ON process_events(stage)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_customer 
                ON projects(customer_id)
            """)
            
            conn.commit()
            print("✅ 데이터베이스 초기화 완료 (v2.2)")
    
            # v0.5: 기본 업체 자동 등록 (최초 1회만)
            _self._init_default_vendors()

    def _init_default_vendors(_self):
        """기본 업체 자동 등록 (v0.5) - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase: 업체 수 확인
            response = _self.supabase.table('vendors').select('vendor_id').execute()
            count = len(response.data)
            
            if count == 0:
                default_vendors = [
                    {'vendor_id': 'NOWORK01', 'vendor_name': '작업없음', 'contact': '', 'process_types': '절단/절곡,P레이저,레이저(판재),벤딩,페인트,스티커,입고', 'memo': '해당 공정 미진행'},
                    {'vendor_id': 'OSEONG01', 'vendor_name': '오성벤딩', 'contact': '010-8050-1000', 'process_types': '벤딩', 'memo': '벤딩 전문업체'},
                    {'vendor_id': 'HWASEONG01', 'vendor_name': '화성공장', 'contact': '', 'process_types': 'P레이저', 'memo': '자가 레이저 가공'},
                    {'vendor_id': 'HYUNDAI01', 'vendor_name': '현대도장', 'contact': '010-8476-5588', 'process_types': '페인트', 'memo': '도장 전문'},
                    {'vendor_id': 'DUSON01', 'vendor_name': '두손레이저', 'contact': '010-8755-9547', 'process_types': '레이저(판재)', 'memo': '판재 레이저 전문'},
                    {'vendor_id': 'HYOSUNG01', 'vendor_name': '효성', 'contact': '010-3712-6207', 'process_types': '절단/절곡', 'memo': '절단 절곡 전문'},
                    {'vendor_id': 'STICKER01', 'vendor_name': '이노텍', 'contact': '010-2120-7375', 'process_types': '스티커', 'memo': '스티커 제작'},
                    {'vendor_id': 'RECEIV01', 'vendor_name': '준비완료', 'contact': '', 'process_types': '입고', 'memo': '제품 준비 완료'}
                ]
                
                for vendor in default_vendors:
                    try:
                        _self.supabase.table('vendors').insert(vendor).execute()
                        print(f"✅ 업체 등록: {vendor['vendor_name']}")
                    except Exception as e:
                        print(f"❌ 업체 등록 실패 ({vendor['vendor_name']}): {e}")
                
                print("✅ 기본 업체 8개 자동 등록 완료")
            else:
                print(f"ℹ️ 이미 {count}개 업체가 등록되어 있어 자동 등록 스킵")
        
        else:
            # SQLite (기존 코드 유지)
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                # ... 기존 코드 그대로 ...
    # ========================================================================
    # CRUD - 고객사 (Customers)
    # ========================================================================
    @st.cache_data(ttl=600) 
    def get_customers(_self):
        """모든 고객사 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('customers').select('*').order('customer_name').execute()
            return pd.DataFrame(response.data)
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                df = pd.read_sql_query("SELECT * FROM customers ORDER BY customer_name", conn)
                return df
    
    def add_customer(_self, customer_id, customer_name, contact=""):
        """고객사 추가"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO customers (customer_id, customer_name, contact)
                VALUES (?, ?, ?)
            """, (customer_id, customer_name, contact))
            return True
    
    def get_customer_by_id(_self, customer_id):
        """특정 고객사 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('customers').select('*').eq('customer_id', customer_id).execute()
            
            if response.data:
                return pd.Series(response.data[0])
            return None
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM customers WHERE customer_id = ?", 
                    conn, 
                    params=(customer_id,)
                )
                return df.iloc[0] if not df.empty else None
    
    # ========================================================================
    # CRUD - 업체 (Vendors) - v0.5 신규
    # ========================================================================
    @st.cache_data(ttl=600)    
    def get_vendors(_self, process_type=None):
        """업체 목록 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('vendors').select('*')
            
            if process_type:
                # Supabase는 LIKE 대신 ilike 사용
                query = query.ilike('process_types', f'%{process_type}%')
            
            query = query.order('vendor_name')
            response = query.execute()
            return pd.DataFrame(response.data)
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                if process_type:
                    query = """
                        SELECT * FROM vendors 
                        WHERE process_types LIKE ? 
                        ORDER BY vendor_name
                    """
                    df = pd.read_sql_query(query, conn, params=(f'%{process_type}%',))
                else:
                    query = "SELECT * FROM vendors ORDER BY vendor_name"
                    df = pd.read_sql_query(query, conn)
                return df
    
    def add_vendor(_self, vendor_id, vendor_name, contact="", process_types="", memo=""):
        """업체 추가"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vendors (vendor_id, vendor_name, contact, process_types, memo)
                VALUES (?, ?, ?, ?, ?)
            """, (vendor_id, vendor_name, contact, process_types, memo))
            return True
    
    def get_vendor_by_id(_self, vendor_id):
        """특정 업체 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('vendors').select('*').eq('vendor_id', vendor_id).execute()
            
            if response.data:
                return pd.Series(response.data[0])
            return None
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM vendors WHERE vendor_id = ?",
                    conn,
                    params=(vendor_id,)
                )
                return df.iloc[0] if not df.empty else None
    
    def update_vendor(_self, vendor_id, **kwargs):
        """업체 정보 수정 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('vendors').update(kwargs).eq('vendor_id', vendor_id).execute()
            return len(response.data) > 0
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                
                set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
                values = list(kwargs.values()) + [vendor_id]
                
                query = f"UPDATE vendors SET {set_clause} WHERE vendor_id = ?"
                cursor.execute(query, values)
                return cursor.rowcount > 0
    
    def delete_vendor(_self, vendor_id):
        """업체 삭제 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('vendors').delete().eq('vendor_id', vendor_id).execute()
            return len(response.data) > 0
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM vendors WHERE vendor_id = ?", (vendor_id,))
                return cursor.rowcount > 0

    # ========================================================================
    # CRUD - 발주 (Orders)
    # ========================================================================
    @st.cache_data(ttl=300)
    def get_orders(_self, customer_id=None):
        """발주 목록 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('orders').select('*')
            
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            query = query.order('due_date', desc=True).order('created_at', desc=True)
            response = query.execute()
            df = pd.DataFrame(response.data)
            
            # 날짜 컬럼 변환
            for col in ['order_date', 'due_date']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            
            return df
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                if customer_id:
                    query = """
                        SELECT * FROM orders 
                        WHERE customer_id = ? 
                        ORDER BY due_date DESC, created_at DESC
                    """
                    df = pd.read_sql_query(query, conn, params=(customer_id,))
                else:
                    query = "SELECT * FROM orders ORDER BY due_date DESC, created_at DESC"
                    df = pd.read_sql_query(query, conn)
                
                # 날짜 컬럼 변환
                for col in ['order_date', 'due_date']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
                
                return df
    
    def add_order(_self, order_id, customer_id, project, vendor, 
            order_date, due_date, status="진행중", memo="", project_id=None):
        """발주 추가 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            data = {
                'order_id': order_id,
                'customer_id': customer_id,
                'project_id': project_id,
                'project': project,
                'vendor': vendor,
                'order_date': str(order_date) if order_date else None,
                'due_date': str(due_date) if due_date else None,
                'status': status,
                'memo': memo
            }
            _self.supabase.table('orders').insert(data).execute()
            print(f"[DB] 발주 추가 성공: {order_id}")
            return True
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orders 
                    (order_id, customer_id, project_id, project, vendor, order_date, due_date, status, memo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order_id, customer_id, project_id, project, vendor, order_date, due_date, status, memo))
                print(f"[DB] 발주 추가 성공: {order_id}")
                return True
    
    def update_order(_self, order_id, **kwargs):
        """발주 수정"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 동적 UPDATE 쿼리 생성
            set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
            set_clause += ", updated_at = CURRENT_TIMESTAMP"
            values = list(kwargs.values()) + [order_id]
            
            query = f"UPDATE orders SET {set_clause} WHERE order_id = ?"
            cursor.execute(query, values)
            return cursor.rowcount > 0
    def delete_order(_self, order_id):
        """발주 삭제 (연관된 items, events도 자동 삭제)"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
            return cursor.rowcount > 0
    @st.cache_data(ttl=300)
    def get_order_by_id(_self, order_id):
        """특정 발주 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('orders').select('*').eq('order_id', order_id).execute()
            
            if response.data:
                order = response.data[0]
                # 날짜 변환
                for col in ['order_date', 'due_date']:
                    if col in order and order[col]:
                        order[col] = pd.to_datetime(order[col]).date()
                return pd.Series(order)
            return None
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM orders WHERE order_id = ?", 
                    conn, 
                    params=(order_id,)
                )
                if not df.empty:
                    for col in ['order_date', 'due_date']:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
                    return df.iloc[0]
                return None
    # ========================================================================
    # CRUD - 발주 품목 (Order Items)
    # ========================================================================
    @st.cache_data(ttl=300)
    def get_order_items(_self, order_id):
        """특정 발주의 품목 조회"""
        with _self.get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM order_items WHERE order_id = ?",
                conn,
                params=(order_id,)
            )
            return df
    
    def add_order_item(_self, order_id, item_name, spec="", quantity="1식"):
        """발주 품목 추가"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO order_items (order_id, item_name, spec, quantity)
                VALUES (?, ?, ?, ?)
            """, (order_id, item_name, spec, quantity))
            return True
    
    def delete_order_item(_self, item_id):
        """발주 품목 삭제"""
        with _self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM order_items WHERE item_id = ?", (item_id,))
            return cursor.rowcount > 0
    
    # ========================================================================
    # CRUD - 공정 이벤트 (Process Events)
    # ========================================================================
    @st.cache_data(ttl=60)
    def get_process_events(_self, order_id=None):
        """공정 이벤트 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('process_events').select('*')
            
            if order_id:
                query = query.eq('order_id', order_id)
            
            query = query.order('created_at', desc=True)
            response = query.execute()
            
            # 🆕 빈 결과 처리
            if not response.data:
                return pd.DataFrame()
            
            df = pd.DataFrame(response.data)
            
            # 날짜 컬럼 변환
            for col in ['planned_date', 'done_date']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
            
            return df
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                if order_id:
                    query = """
                        SELECT * FROM process_events 
                        WHERE order_id = ? 
                        ORDER BY created_at DESC
                    """
                    df = pd.read_sql_query(query, conn, params=(order_id,))
                else:
                    query = "SELECT * FROM process_events ORDER BY created_at DESC"
                    df = pd.read_sql_query(query, conn)
                
                # 날짜 컬럼 변환
                for col in ['planned_date', 'done_date']:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce').dt.date
                
                return df
    # mutation: do not cache
    def add_process_event(_self, order_id, stage, progress=0, 
                        planned_date=None, done_date=None, vendor=None, note=""):
        """공정 이벤트 추가 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전 - 성능 최적화
            data = {
                'order_id': order_id,
                'stage': stage,
                'progress': progress,
                'planned_date': str(planned_date) if planned_date else None,
                'done_date': str(done_date) if done_date else None,
                'vendor': vendor,
                'note': note,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # ⚡ 성능 최적화: 단일 API 호출로 병합
            try:
                # 이벤트 추가
                _self.supabase.table('process_events').insert(data).execute()

                # 완료 처리일 때만 현재 공정 단계 갱신 및 상태 업데이트
                if progress >= 100 or done_date:
                    _self.supabase.table('orders').update({
                        'current_stage': stage,
                        'status': '완료'
                    }).eq('order_id', order_id).execute()
                else:
                    # 해제(미완료 전환) 시 상태를 진행중으로 되돌림
                    _self.supabase.table('orders').update({
                        'status': '진행중'
                    }).eq('order_id', order_id).execute()

                return True
                
            except Exception as e:
                print(f"⚠️ 이벤트 추가 실패 ({order_id}, {stage}): {e}")
                return False
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO process_events 
                    (order_id, stage, progress, planned_date, done_date, vendor, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (order_id, stage, progress, planned_date, done_date, vendor, note))
                # 완료 처리일 때만 현재 공정 단계 갱신
                if progress >= 100 or (done_date is not None):
                    cursor.execute("""
                        UPDATE orders 
                        SET current_stage = ?,
                            status = '완료',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE order_id = ?
                    """, (stage, order_id))
                else:
                    # 해제 시 진행중으로 되돌림
                    cursor.execute("""
                        UPDATE orders
                        SET status = '진행중',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE order_id = ?
                    """, (order_id,))

                return True
    @st.cache_data(ttl=60)
    def get_latest_events_by_stage(_self, order_id):
        """발주별 각 공정의 최신 이벤트 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('process_events')\
                .select('*')\
                .eq('order_id', order_id)\
                .order('created_at', desc=True)\
                .execute()
            
            if not response.data:
                return pd.DataFrame()
            
            df = pd.DataFrame(response.data)
            
            # 각 공정(process_stage)별로 최신 이벤트만 추출
            # stage 컬럼이 있는지 확인하고 그룹화
            # created_at 기준 정렬 후 공정별 최신 1건만 유지
            try:
                if 'created_at' in df.columns:
                    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
                sort_cols = []
                if 'created_at' in df.columns:
                    sort_cols.append('created_at')
                if 'event_id' in df.columns:
                    sort_cols.append('event_id')
                if sort_cols:
                    df = df.sort_values(sort_cols, ascending=[False]*len(sort_cols))
            except Exception:
                pass

            if 'stage' in df.columns:
                latest_events = df.drop_duplicates(subset='stage', keep='first')
            elif 'process_stage' in df.columns:
                latest_events = df.drop_duplicates(subset='process_stage', keep='first')
            else:
                latest_events = df
            
            # 날짜 변환
            for col in ['planned_date', 'done_date']:
                if col in latest_events.columns:
                    latest_events[col] = pd.to_datetime(latest_events[col], errors='coerce').dt.date
            if 'created_at' in latest_events.columns:
                latest_events['created_at'] = pd.to_datetime(latest_events['created_at'])
            
            return latest_events
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                query = """
                    SELECT * FROM process_events
                    WHERE order_id = ?
                    ORDER BY created_at DESC, event_id DESC
                """
                df = pd.read_sql_query(query, conn, params=(order_id,))
                
                if df.empty:
                    return df
                
                # 각 공정(stage)별로 최신 이벤트만 추출
                latest_events = df.groupby('stage').first().reset_index()
                
                # 날짜 변환
                for col in ['planned_date', 'done_date']:
                    if col in latest_events.columns:
                        latest_events[col] = pd.to_datetime(latest_events[col], errors='coerce').dt.date
                if 'created_at' in latest_events.columns:
                    latest_events['created_at'] = pd.to_datetime(latest_events['created_at'], errors='coerce')
                # 정렬 안정화: 동일 타임스탬프 시 event_id 기준으로 최신 선택
                try:
                    base_df = df.copy() if 'df' in locals() else latest_events
                    if 'created_at' in base_df.columns:
                        base_df['created_at'] = pd.to_datetime(base_df['created_at'], errors='coerce')
                    sort_cols = []
                    if 'created_at' in base_df.columns:
                        sort_cols.append('created_at')
                    if 'event_id' in base_df.columns:
                        sort_cols.append('event_id')
                    if sort_cols:
                        base_df = base_df.sort_values(sort_cols, ascending=[False]*len(sort_cols))
                    if 'stage' in base_df.columns:
                        latest_events = base_df.drop_duplicates(subset='stage', keep='first')
                except Exception:
                    pass
                
                return latest_events
    # ========================================================================
    # CRUD - 프로젝트 (Projects)
    # ========================================================================
    @st.cache_data(ttl=300)    
    def get_projects(_self, customer_id=None):
        """프로젝트 목록 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # 🆕 Supabase 버전
            query = _self.supabase.table('projects').select('*')
            
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            query = query.order('final_due_date')
            response = query.execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty and 'final_due_date' in df.columns:
                df['final_due_date'] = pd.to_datetime(df['final_due_date'], errors='coerce').dt.date
            
            return df
        
        else:
            # ✅ 기존 SQLite 버전
            with _self.get_connection() as conn:
                if customer_id:
                    query = "SELECT * FROM projects WHERE customer_id = ? ORDER BY final_due_date"
                    df = pd.read_sql_query(query, conn, params=(customer_id,))
                else:
                    query = "SELECT * FROM projects ORDER BY final_due_date"
                    df = pd.read_sql_query(query, conn)
                
                if not df.empty and 'final_due_date' in df.columns:
                    df['final_due_date'] = pd.to_datetime(df['final_due_date'], errors='coerce').dt.date
                
                return df
    
    def add_project(_self, project_id, project_name, customer_id, final_due_date,
                    status="진행중", memo="", contract_type="관급", contract_amount=0):
        """프로젝트 추가 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            data = {
                'project_id': project_id,
                'project_name': project_name,
                'customer_id': customer_id,
                'final_due_date': str(final_due_date),
                'status': status,
                'memo': memo,
                'contract_type': contract_type,
                'contract_amount': contract_amount
            }
            _self.supabase.table('projects').insert(data).execute()
            return True
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO projects 
                    (project_id, project_name, customer_id, final_due_date, status, memo, contract_type, contract_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (project_id, project_name, customer_id, final_due_date, status, memo, contract_type, contract_amount))
                return True
    @st.cache_data(ttl=300)
    def get_project_by_id(_self, project_id):
        """특정 프로젝트 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('projects').select('*').eq('project_id', project_id).execute()
            
            if response.data:
                project = response.data[0]
                # 날짜 변환
                if 'final_due_date' in project and project['final_due_date']:
                    project['final_due_date'] = pd.to_datetime(project['final_due_date']).date()
                return pd.Series(project)
            return None
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM projects WHERE project_id = ?",
                    conn,
                    params=(project_id,)
                )
                if not df.empty:
                    if 'final_due_date' in df.columns:
                        df['final_due_date'] = pd.to_datetime(df['final_due_date'], errors='coerce').dt.date
                    return df.iloc[0]
                return None
    @st.cache_data(ttl=300)
    def get_project_by_name(_self, project_name, customer_id=None):
        """프로젝트명으로 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('projects').select('*').eq('project_name', project_name)
            
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            response = query.execute()
            
            if response.data:
                project = response.data[0]
                # 날짜 변환
                if 'final_due_date' in project and project['final_due_date']:
                    project['final_due_date'] = pd.to_datetime(project['final_due_date']).date()
                return pd.Series(project)
            return None
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                if customer_id:
                    query = "SELECT * FROM projects WHERE project_name = ? AND customer_id = ?"
                    df = pd.read_sql_query(query, conn, params=(project_name, customer_id))
                else:
                    query = "SELECT * FROM projects WHERE project_name = ?"
                    df = pd.read_sql_query(query, conn, params=(project_name,))
                
                if not df.empty:
                    if 'final_due_date' in df.columns:
                        df['final_due_date'] = pd.to_datetime(df['final_due_date'], errors='coerce').dt.date
                    return df.iloc[0]
                return None
     
    def generate_order_id(_self, project_id, vendor_type):
        """발주번호 자동 생성 - Supabase/SQLite 분기
        Args:
            project_id: PRJ-고덕초01
            vendor_type: LASER, BAND, PAINT 등
        Returns:
            ORD-고덕초01-LASER-01
        """
        # 프로젝트 정보 가져오기
        project = _self.get_project_by_id(project_id)
        if project is None:
            return None
        
        # 프로젝트 이니셜 추출 (PRJ-고덕초01 → 고덕초01)
        project_code = project_id.replace("PRJ-", "")
        
        if USE_SUPABASE:
            # Supabase 버전
            response = _self.supabase.table('orders')\
                .select('order_id')\
                .eq('project_id', project_id)\
                .like('order_id', f'ORD-{project_code}-{vendor_type}-%')\
                .execute()
            
            count = len(response.data)
            next_num = count + 1
            
            order_id = f"ORD-{project_code}-{vendor_type}-{next_num:02d}"
            return order_id
        
        else:
            # SQLite 버전
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM orders 
                    WHERE project_id = ? AND order_id LIKE ?
                """, (project_id, f"ORD-{project_code}-{vendor_type}-%"))
                
                count = cursor.fetchone()[0]
                next_num = count + 1
                
                order_id = f"ORD-{project_code}-{vendor_type}-{next_num:02d}"
                return order_id
        
    # ==================== 통계 함수 (v0.5) ====================
    @st.cache_data(ttl=60)
    def get_sales_statistics(_self, year=None, month=None, customer_id=None):
        """매출 통계 조회 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('projects')\
                .select('final_due_date, contract_type, contract_amount')\
                .eq('status', '완료')
            
            # 🆕 업체별 필터링 추가
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            response = query.execute()
            
            if not response.data:
                return []
            
            import pandas as pd
            df = pd.DataFrame(response.data)
            df['final_due_date'] = pd.to_datetime(df['final_due_date'])
            df['year'] = df['final_due_date'].dt.strftime('%Y')
            df['month'] = df['final_due_date'].dt.strftime('%m')
            
            # 필터 적용
            if year:
                df = df[df['year'] == str(year)]
            if month:
                df = df[df['month'] == f'{month:02d}']
            
            # 그룹화 및 집계
            results = []
            for (y, m, ct), group in df.groupby(['year', 'month', 'contract_type']):
                results.append({
                    'year': y,
                    'month': m,
                    'contract_type': ct,
                    'project_count': len(group),
                    'total_amount': group['contract_amount'].sum(),
                    'avg_amount': group['contract_amount'].mean()
                })
            
            return results
        
        else:
            # SQLite 버전 (기존 코드 유지)
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        strftime('%Y', final_due_date) as year,
                        strftime('%m', final_due_date) as month,
                        contract_type,
                        COUNT(*) as project_count,
                        SUM(contract_amount) as total_amount,
                        AVG(contract_amount) as avg_amount
                    FROM projects
                    WHERE status = '완료'
                """
                
                conditions = []
                if year:
                    conditions.append(f"AND strftime('%Y', final_due_date) = '{year}'")
                if month:
                    conditions.append(f"AND strftime('%m', final_due_date) = '{month:02d}'")
                
                if conditions:
                    query += " " + " ".join(conditions)
                
                query += """
                    GROUP BY year, month, contract_type
                    ORDER BY year DESC, month DESC
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        'year': row[0],
                        'month': row[1],
                        'contract_type': row[2],
                        'project_count': row[3],
                        'total_amount': row[4] or 0,
                        'avg_amount': row[5] or 0
                    })
                
                return results
    @st.cache_data(ttl=60)
    def get_monthly_sales_trend(_self, months=12, customer_id=None):
        """월별 매출 추이 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            from datetime import datetime, timedelta
            
            # 12개월 전 날짜 계산
            start_date = (datetime.now() - timedelta(days=months*30)).strftime('%Y-%m-%d')
            
            query = _self.supabase.table('projects')\
                .select('final_due_date, contract_type, contract_amount')\
                .eq('status', '완료')\
                .gte('final_due_date', start_date)
            
            # 🆕 업체별 필터링 추가
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            response = query.execute()
            
            if not response.data:
                return []
            
            import pandas as pd
            df = pd.DataFrame(response.data)
            df['final_due_date'] = pd.to_datetime(df['final_due_date'])
            df['month'] = df['final_due_date'].dt.strftime('%Y-%m')
            
            # 그룹화
            results = []
            for (month, ct), group in df.groupby(['month', 'contract_type']):
                results.append({
                    'month': month,
                    'contract_type': ct,
                    'total_amount': group['contract_amount'].sum()
                })
            
            return sorted(results, key=lambda x: x['month'], reverse=True)
        
        else:
            # SQLite 버전 (기존 코드)
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        strftime('%Y-%m', final_due_date) as month,
                        contract_type,
                        SUM(contract_amount) as total_amount
                    FROM projects
                    WHERE status = '완료'
                        AND final_due_date >= date('now', '-' || ? || ' months')
                """
                
                # 🆕 업체별 필터링 추가
                conditions = []
                if customer_id:
                    conditions.append("AND customer_id = ?")
                
                if conditions:
                    query += " " + " ".join(conditions)
                
                query += """
                    GROUP BY month, contract_type
                    ORDER BY month DESC
                """
                
                params = [months]
                if customer_id:
                    params.append(customer_id)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        'month': row[0],
                        'contract_type': row[1],
                        'total_amount': row[2] or 0
                    })
                
                return results
    @st.cache_data(ttl=60)
    def get_contract_type_ratio(_self, year=None, customer_id=None):
        """관급/사급 비율 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('projects')\
                .select('final_due_date, contract_type, contract_amount')\
                .eq('status', '완료')
            
            # 🆕 업체별 필터링 추가
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            response = query.execute()
            
            if not response.data:
                return []
            
            import pandas as pd
            df = pd.DataFrame(response.data)
            
            # 연도 필터
            if year:
                df['final_due_date'] = pd.to_datetime(df['final_due_date'])
                df = df[df['final_due_date'].dt.year == int(year)]
            
            # 그룹화
            results = []
            for ct, group in df.groupby('contract_type'):
                results.append({
                    'contract_type': ct,
                    'count': len(group),
                    'total_amount': group['contract_amount'].sum()
                })
            
            return results
        
        else:
            # SQLite 버전 (기존 코드)
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        contract_type,
                        COUNT(*) as count,
                        SUM(contract_amount) as total_amount
                    FROM projects
                    WHERE status = '완료'
                """
                
                conditions = []
                if year:
                    conditions.append(f"AND strftime('%Y', final_due_date) = '{year}'")
                if customer_id:
                    conditions.append("AND customer_id = ?")
                
                if conditions:
                    query += " " + " ".join(conditions)
                
                query += " GROUP BY contract_type"
                
                params = []
                if customer_id:
                    params.append(customer_id)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        'contract_type': row[0],
                        'count': row[1],
                        'total_amount': row[2] or 0
                    })
                
                return results
    @st.cache_data(ttl=60)
    def get_top_projects_by_amount(_self, limit=10, year=None, customer_id=None):
        """계약금액 상위 프로젝트 - Supabase/SQLite 분기"""
        
        if USE_SUPABASE:
            # Supabase 버전
            query = _self.supabase.table('projects')\
                .select('project_id, project_name, contract_type, contract_amount, final_due_date, installation_completed_date')\
                .eq('status', '완료')\
                .gt('contract_amount', 0)
            
            # 🆕 업체별 필터링 추가
            if customer_id:
                query = query.eq('customer_id', customer_id)
            
            response = query.execute()
            
            if not response.data:
                return []
            
            import pandas as pd
            df = pd.DataFrame(response.data)
            
            # 연도 필터
            if year:
                df['final_due_date'] = pd.to_datetime(df['final_due_date'])
                df = df[df['final_due_date'].dt.year == int(year)]
            
            # 정렬 및 상위 N개
            df = df.sort_values('contract_amount', ascending=False).head(limit)
            
            results = []
            for _, row in df.iterrows():
                results.append({
                    'project_id': row['project_id'],
                    'project_name': row['project_name'],
                    'contract_type': row['contract_type'],
                    'contract_amount': row['contract_amount'],
                    'final_due_date': row['final_due_date'],
                    'installation_completed_date': row.get('installation_completed_date')
                })
            
            return results
        
        else:
            # SQLite 버전 (기존 코드)
            with _self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT 
                        project_id,
                        project_name,
                        contract_type,
                        contract_amount,
                        final_due_date,
                        installation_completed_date
                    FROM projects
                    WHERE status = '완료'
                        AND contract_amount > 0
                """
                
                conditions = []
                if year:
                    conditions.append(f"AND strftime('%Y', final_due_date) = '{year}'")
                if customer_id:
                    conditions.append("AND customer_id = ?")
                
                if conditions:
                    query += " " + " ".join(conditions)
                
                query += """
                    ORDER BY contract_amount DESC
                    LIMIT ?
                """
                
                params = [limit]
                if customer_id:
                    params.append(customer_id)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    results.append({
                        'project_id': row[0],
                        'project_name': row[1],
                        'contract_type': row[2],
                        'contract_amount': row[3],
                        'final_due_date': row[4],
                        'installation_completed_date': row[5]
                    })
                
                return results

# ============================================================================
# 비즈니스 로직 클래스
# ============================================================================

class WIPManager:
    """WIP 현황 관리 비즈니스 로직"""
    
    def __init__(_self, db_manager):
        _self.db = db_manager
        _self.stages = ["절단/절곡", "레이저", "벤딩", "페인트", "스티커", "입고"]
        _self.stage_colors = {
            "절단/절곡": "#FF6B6B",
            "P레이저": "#45B7D1",
            "레이저(판재)": "#45B7D1",
            "벤딩": "#4ECDC4",            
            "페인트": "#96CEB4",
            "스티커": "#6C5CE2",
            "입고": "#6C5CE7"
        }
    
    def calculate_order_progress(_self, order_id):
        """발주의 진행률 계산"""
        events = _self.db.get_latest_events_by_stage(order_id)
        
        if events.empty:
            return {
                'progress_pct': 0,
                'current_stage': '미시작',
                'stage_status': {stage: '대기' for stage in _self.stages}
            }
        
        stage_status = {}
        completed_count = 0
        current_stage = '미시작'
        
        for stage in _self.stages:
            stage_events = events[events['stage'] == stage]
            
            if stage_events.empty:
                stage_status[stage] = '대기'
            else:
                event = stage_events.iloc[0]
                # 완료 조건 수정: done_date만 체크
                if pd.notna(event.get('done_date')):
                    stage_status[stage] = '완료'
                    completed_count += 1
                elif event.get('progress', 0) >= 100:
                    stage_status[stage] = '완료'
                    completed_count += 1
                else:
                    stage_status[stage] = '진행중'
                    if current_stage == '미시작':
                        current_stage = stage
        
        # 모든 단계 완료 체크
        if completed_count == len(_self.stages):
            current_stage = '완료'
        elif current_stage == '미시작' and completed_count > 0:
            # 다음 대기 단계 찾기
            for stage in _self.stages:
                if stage_status[stage] == '대기':
                    current_stage = stage
                    break
        
        progress_pct = int((completed_count / len(_self.stages)) * 100)
        
        return {
            'progress_pct': progress_pct,
            'current_stage': current_stage,
            'stage_status': stage_status
        }
    @st.cache_data(ttl=300)
    def get_orders_with_progress(_self, customer_id=None):
        """진행률이 포함된 발주 목록 조회"""
        orders = _self.db.get_orders(customer_id)
        
        if orders.empty:
            return orders
        
        # current_stage 컬럼이 없으면 추가
        if 'current_stage' not in orders.columns:
            orders['current_stage'] = '미시작'
        
        # 각 발주의 진행률 계산
        progress_data = []
        for _, order in orders.iterrows():
            progress_info = _self.calculate_order_progress(order['order_id'])
            progress_data.append({
                'order_id': order['order_id'],
                **progress_info
            })
        
        progress_df = pd.DataFrame(progress_data)
        
        # 원본 데이터와 병합
        result = orders.merge(progress_df, on='order_id', how='left', suffixes=('_db', '_calc'))
        
        # current_stage는 계산된 값 사용 (DB 값은 무시)
        if 'current_stage_calc' in result.columns:
            result['current_stage'] = result['current_stage_calc']
            result.drop(['current_stage_db', 'current_stage_calc'], axis=1, inplace=True, errors='ignore')
        
        # 기본값 설정
        result['progress_pct'] = result['progress_pct'].fillna(0).astype(int)
        result['current_stage'] = result['current_stage'].fillna('미시작')
        
        return result
    @st.cache_data
    def get_dashboard_stats(_self, customer_id=None):
        """대시보드 통계 계산"""
        orders = _self.get_orders_with_progress(customer_id)
        
        if orders.empty:
            return {
                'total': 0,
                'wip': 0,
                'completed': 0,
                'overdue': 0,
                'thisweek_due': 0
            }
        
        today = date.today()
        week_end = today + timedelta(days=7)
        
        total = len(orders)
        completed = len(orders[orders['progress_pct'] >= 100])
        wip = total - completed
        
        # 지연 계산
        overdue = len(orders[
            (orders['due_date'].notna()) &
            (orders['due_date'] < today) &
            (orders['progress_pct'] < 100)
        ])
        
        # 이번주 완료 예정
        thisweek_due = len(orders[
            (orders['due_date'].notna()) &
            (orders['due_date'] >= today) &
            (orders['due_date'] <= week_end) &
            (orders['progress_pct'] < 100)
        ])
        
        return {
            'total': total,
            'wip': wip,
            'completed': completed,
            'overdue': overdue,
            'thisweek_due': thisweek_due
        }
    
    def is_order_delayed(_self, order):
        """발주 지연 여부 확인"""
        if pd.isna(order['due_date']):
            return False
        
        # 문자열이면 date로 변환
        due_date = order['due_date']
        if isinstance(due_date, str):
            try:
                due_date = pd.to_datetime(due_date).date()
            except:
                return False
        
        today = date.today()
        return due_date < today and order['progress_pct'] < 100
    @st.cache_data
    def get_stage_emoji(_self, status):
        """단계 상태별 이모지 반환"""
        emoji_map = {
            '완료': '✅',
            '진행중': '🟡',
            '대기': '⚪'
        }
        return emoji_map.get(status, '⚪')
    
    def format_stage_chips(_self, stage_status):
        """단계별 상태 칩 포맷팅"""
        if not stage_status:
            return "미시작"
        
        chips = []
        for stage in _self.stages:
            status = stage_status.get(stage, '대기')
            emoji = _self.get_stage_emoji(status)
            chips.append(f"{emoji} {stage}")
        
        return " | ".join(chips)
    
    def create_sample_data(_self):
        """샘플 데이터 생성 - v2.2 프로젝트 포함"""
        today = date.today()
        
        # 1. 고객사 추가
        try:
            _self.db.add_customer("DOOHO", "두호", "010-1234-5678")
            print("✅ 고객사 추가 완료")
        except Exception as e:
            print(f"고객사 추가 스킵 (이미 존재): {e}")

        # 1.5. 업체 추가 (v0.5 신규)
        vendors_to_add = [
            {
                'vendor_id': 'OSEONG01',
                'vendor_name': '오성벤딩',
                'contact': '010-8050-1000',
                'process_types': '벤딩',
                'memo': '벤딩 전문업체'
            },
            {
                'vendor_id': 'HWASEONG01',
                'vendor_name': '화성공장',
                'contact': '',
                'process_types': 'P레이저',
                'memo': '자가 레이저 가공'
            },
            {
                'vendor_id': 'HYUNDAI01',
                'vendor_name': '현대도장',
                'contact': '010-8476-5588',
                'process_types': '페인트',
                'memo': '도장 전문'
            },
            {
                'vendor_id': 'DUSON01',
                'vendor_name': '두손레이저',
                'contact': '010-8755-9547',
                'process_types': '레이저(판재)',
                'memo': '판재 레이저 전문'
            },
            {
                'vendor_id': 'HYOSUNG01',
                'vendor_name': '효성',
                'contact': '010-3712-6207',
                'process_types': '절단/절곡',
                'memo': '절단 절곡 전문'
            }
        ]
        
        for vendor in vendors_to_add:
            try:
                _self.db.add_vendor(**vendor)
                print(f"✅ 업체 추가: {vendor['vendor_name']}")
            except Exception as e:
                print(f"업체 추가 스킵: {e}")    
        
        # 2. 프로젝트 추가
        projects_to_add = [
            {
                'project_id': 'PRJ-시흥초01',
                'project_name': '시흥초등학교',
                'customer_id': 'DOOHO',
                'final_due_date': today + timedelta(days=10),
                'status': '진행중',
                'memo': '학교 휀스 및 차양 설치'
            },
            {
                'project_id': 'PRJ-진말초01',
                'project_name': '진말초등학교',
                'customer_id': 'DOOHO',
                'final_due_date': today + timedelta(days=5),
                'status': '진행중',
                'memo': '아파트 자전거보관대'
            }
        ]
        
        for proj in projects_to_add:
            try:
                _self.db.add_project(**proj)
                print(f"✅ 프로젝트 추가: {proj['project_id']}")
            except Exception as e:
                print(f"프로젝트 추가 스킵: {e}")
        
        # 3. 발주 추가
        orders_to_add = [
            {
                'order_id': 'ORD-시흥초01-LASER-01',
                'customer_id': 'DOOHO',
                'project_id': 'PRJ-시흥초01',
                'project': '시흥초등학교',
                'vendor': '화성공장',
                'order_date': today - timedelta(days=10),
                'due_date': today - timedelta(days=2),
                'status': '완료',
                'memo': '휀스 홀 가공'
            },
            {
                'order_id': 'ORD-진말초01-BAND-01',
                'customer_id': 'DOOHO',
                'project_id': 'PRJ-진말초01',
                'project': '진말초등학교',
                'vendor': '오성벤딩',
                'order_date': today - timedelta(days=8),
                'due_date': today + timedelta(days=3),
                'status': '진행중',
                'memo': '횡대 벤딩 '
            },
            {
                'order_id': 'ORD-라라중01-PAINT-01',
                'customer_id': 'DOOHO',
                'project_id': 'PRJ-라라중01',
                'project': '라라중학교',
                'vendor': '현대도장',
                'order_date': today - timedelta(days=6),
                'due_date': today + timedelta(days=4),
                'status': '진행중',
                'memo': '기와진회색'
            }
        ]
        
        for order in orders_to_add:
            try:
                _self.db.add_order(**order)
                print(f"✅ 발주 추가: {order['order_id']}")
            except Exception as e:
                print(f"발주 추가 스킵: {e}")
        
        # 4. 이벤트 추가
        events_to_add = [
            ('ORD-시흥초01-LASER-01', '레이저', 100, today - timedelta(days=9)),
            ('ORD-시흥초01-LASER-01', '레이저', 100, today - timedelta(days=7)),
            ('ORD-시흥초01-LASER-01', '입고', 100, today - timedelta(days=2)),
            ('ORD-라라중01-BAND-01', '벤딩', 100, today - timedelta(days=5)),
            ('ORD-라라중01-CUT-01', '절단/절곡', 50, None),
            ('ORD-라라중01-PAINT-01', '페인트', 30, None),
        ]
        
        for order_id, stage, progress, done_date in events_to_add:
            try:
                _self.db.add_process_event(
                    order_id=order_id,
                    stage=stage,
                    progress=progress,
                    done_date=done_date
                )
                print(f"✅ 이벤트 추가: {order_id} - {stage}")
            except Exception as e:
                print(f"이벤트 추가 스킵: {e}")
        
        print("✅ 샘플 데이터 생성 완료")
        return True
    @st.cache_data(ttl=300)
    def get_projects_with_orders(_self, customer_id=None):
        """프로젝트별 발주 현황 집계"""
        projects = _self.db.get_projects(customer_id)
        
        if projects.empty:
            return pd.DataFrame()
        
        result = []
        # fetch orders once to avoid repeated cached calls
        orders_all = _self.db.get_orders()
        for _, project in projects.iterrows():
            project_orders = orders_all[orders_all['project_id'] == project['project_id']]
            
            if not project_orders.empty:
                total_orders = len(project_orders)
                completed_orders = 0
                
                for _, order in project_orders.iterrows():
                    order_parts = order['order_id'].split('-')
                    if len(order_parts) >= 3:
                        process_type = order_parts[2]
                        
                        process_map = {
                            'CUT': '절단/절곡',
                            'PLASER': 'P레이저',
                            'LASER': '레이저(판재)',
                            'BAND': '벤딩',
                            'PAINT': '페인트',
                            'STICKER': '스티커',
                            'RECEIVING': '입고'
                        }
                        
                        target_stage = process_map.get(process_type)
                        
                        if target_stage:
                            events = _self.db.get_process_events(order['order_id'])
                            # 🆕 빈 DataFrame 체크 추가
                            if events.empty:
                                continue
                                
                            stage_events = events[events['stage'] == target_stage]
                            
                            if not stage_events.empty:
                                latest_event = stage_events.iloc[0]
                                is_done = pd.notna(latest_event.get('done_date')) or latest_event.get('progress', 0) >= 100
                                
                                if is_done:
                                    completed_orders += 1
                
                total_progress = int((completed_orders / total_orders) * 100) if total_orders > 0 else 0
            else:
                total_progress = 0
            
            warning_level, d_day = _self.get_project_warning_level(project['final_due_date'])
            
            result.append({
                'project_id': project['project_id'],
                'project_name': project['project_name'],
                'contract_type': project.get('contract_type', '관급'),
                'contract_amount': project.get('contract_amount', 0),
                'final_due_date': project['final_due_date'],
                'installation_completed_date': project.get('installation_completed_date'),
                'installation_staff_count': project.get('installation_staff_count'),
                'installation_days': project.get('installation_days'),
                'tax_invoice_issued': project.get('tax_invoice_issued', False),
                'trade_statement_issued': project.get('trade_statement_issued', False),
                'status': project['status'],
                'order_count': len(project_orders),
                'total_progress': int(total_progress),
                'warning_level': warning_level,
                'd_day': d_day
            })
        
        return pd.DataFrame(result)
    
    def update_project_installation(_self, project_id, completed_date=None, staff_count=None, days=None):
        """프로젝트 설치 정보 업데이트"""
        
        update_data = {}
        
        if completed_date is not None:
            update_data['installation_completed_date'] = completed_date
        
        if staff_count is not None:
            update_data['installation_staff_count'] = staff_count
        
        if days is not None:
            update_data['installation_days'] = days
        
        if update_data:
            # DatabaseManager에 update_project 메서드가 있다면 사용
            # 없다면 직접 분기 처리
            if USE_SUPABASE:
                # str 변환
                if 'installation_completed_date' in update_data:
                    update_data['installation_completed_date'] = str(update_data['installation_completed_date']) if update_data['installation_completed_date'] else None
                
                _self.db.supabase.table('projects').update(update_data).eq('project_id', project_id).execute()
                return True
            else:
                with _self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    updates = []
                    params = []
                    
                    if completed_date is not None:
                        updates.append("installation_completed_date = ?")
                        params.append(completed_date)
                    
                    if staff_count is not None:
                        updates.append("installation_staff_count = ?")
                        params.append(staff_count)
                    
                    if days is not None:
                        updates.append("installation_days = ?")
                        params.append(days)
                    
                    if updates:
                        query = f"UPDATE projects SET {', '.join(updates)} WHERE project_id = ?"
                        params.append(project_id)
                        cursor.execute(query, params)
                        return True
        
        return False
    
    def update_project_documents(_self, project_id, tax_invoice=None, trade_statement=None):
        """프로젝트 서류 발행 상태 업데이트"""
        
        if USE_SUPABASE:
            update_data = {}
            if tax_invoice is not None:
                update_data['tax_invoice_issued'] = tax_invoice
            if trade_statement is not None:
                update_data['trade_statement_issued'] = trade_statement
            
            if update_data:
                _self.db.supabase.table('projects').update(update_data).eq('project_id', project_id).execute()
                return True
            return False
        
        else:
            with _self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                updates = []
                params = []
                
                if tax_invoice is not None:
                    updates.append("tax_invoice_issued = ?")
                    params.append(1 if tax_invoice else 0)
                
                if trade_statement is not None:
                    updates.append("trade_statement_issued = ?")
                    params.append(1 if trade_statement else 0)
                
                if updates:
                    query = f"UPDATE projects SET {', '.join(updates)} WHERE project_id = ?"
                    params.append(project_id)
                    cursor.execute(query, params)
                    return True
                
                return False
    @st.cache_data(ttl=300)
    def get_project_completion_status(_self, project_id):
        """프로젝트 완료 조건 체크 (관급/사급 구분)"""
        project = _self.db.get_project_by_id(project_id)
        if project is None:
            return {'completed': False, 'reason': '프로젝트를 찾을 수 없습니다'}
        
        orders = _self.db.get_orders()
        project_orders = orders[orders['project_id'] == project_id]
        
        if project_orders.empty:
            return {'completed': False, 'reason': '발주 내역이 없습니다'}
        
        # 각 발주의 담당 공정 완료 확인
        all_completed = True
        for _, order in project_orders.iterrows():
            order_parts = order['order_id'].split('-')
            if len(order_parts) >= 3:
                process_type = order_parts[2]
                
                process_map = {
                    'CUT': '절단/절곡',
                    'PLASER': 'P레이저',
                    'LASER': '레이저(판재)',
                    'BAND': '벤딩',
                    'PAINT': '페인트',
                    'STICKER': '스티커',
                    'RECEIVING': '입고'
                }
                
                target_stage = process_map.get(process_type)
                
                if target_stage:
                    events = _self.db.get_process_events(order['order_id'])

                    # 빈 DataFrame 체크
                    if events.empty:
                        all_completed = False
                        break

                    # 'stage' 또는 'process_stage' 컬럼명 확인
                    if 'stage' in events.columns:
                        stage_events = events[events['stage'] == target_stage]
                    elif 'process_stage' in events.columns:
                        stage_events = events[events['process_stage'] == target_stage]
                    else:
                        # 컬럼이 없으면 미완료로 처리
                        all_completed = False
                        break
                    
                    if stage_events.empty or (pd.isna(stage_events.iloc[0]['done_date']) and stage_events.iloc[0]['progress'] < 100):
                        all_completed = False
                        break
        
        if not all_completed:
            return {'completed': False, 'reason': '모든 발주가 완료되지 않았습니다'}
        
        # 설치 완료일 확인
        install_date = project.get('installation_completed_date')
        if isinstance(install_date, pd.Series):
            install_date = install_date.iloc[0] if not install_date.empty else None
        
        if pd.isna(install_date) or install_date == '':
            return {'completed': False, 'reason': '설치완료일이 입력되지 않았습니다'}
        
        # 관급/사급 분기
        contract_type = project.get('contract_type', '관급')
        if isinstance(contract_type, pd.Series):
            contract_type = contract_type.iloc[0]
        
        if contract_type == '사급':
            tax = project.get('tax_invoice_issued', False)
            trade = project.get('trade_statement_issued', False)
            
            if isinstance(tax, pd.Series):
                tax = tax.iloc[0]
            if isinstance(trade, pd.Series):
                trade = trade.iloc[0]
            
            if not tax or not trade:
                return {'completed': False, 'reason': '세금계산서 또는 거래명세서가 발행되지 않았습니다'}
        
        return {'completed': True, 'reason': '완료 조건을 모두 충족했습니다'}

    def auto_update_project_status(_self, project_id):
        """프로젝트 상태 자동 업데이트 - Supabase/SQLite 분기"""
        completion_status = _self.get_project_completion_status(project_id)
        
        if completion_status['completed']:
            # 완료 조건 충족 → 완료로 변경
            if USE_SUPABASE:
                _self.db.supabase.table('projects').update({
                    'status': '완료'
                }).eq('project_id', project_id).execute()
            else:
                with _self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE projects SET status = '완료' WHERE project_id = ?",
                        (project_id,)
                    )
            return True
        else:
            # 완료 조건 미충족 → 진행중으로 변경 (완료였던 경우만)
            project = _self.db.get_project_by_id(project_id)
            
            if project is None:
                return False
            
            current_status = project.get('status')
            if isinstance(current_status, pd.Series):
                current_status = current_status.iloc[0] if not current_status.empty else None
            
            if current_status == '완료':
                # 완료였는데 조건 미충족 → 진행중으로 되돌림
                if USE_SUPABASE:
                    _self.db.supabase.table('projects').update({
                        'status': '진행중'
                    }).eq('project_id', project_id).execute()
                else:
                    with _self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE projects SET status = '진행중' WHERE project_id = ?",
                            (project_id,)
                        )
                return True
        
        return False
    @st.cache_data(ttl=300)
    def get_project_warning_level(_self, final_due_date):
        """프로젝트 납기 경고 레벨 반환"""
        if pd.isna(final_due_date):
            return "normal", ""
        
        if isinstance(final_due_date, str):
            try:
                final_due_date = pd.to_datetime(final_due_date).date()
            except:
                return "normal", ""
        
        today = date.today()
        days_left = (final_due_date - today).days
        
        if days_left < 0:
            return "overdue", f"D+{abs(days_left)}"
        elif days_left <= 7:
            return "urgent", f"D-{days_left}"
        elif days_left <= 14:
            return "warning", f"D-{days_left}"
        else:
            return "normal", f"D-{days_left}"
    
    def apply_filters_to_projects(_self, projects_df):
        """프로젝트에 필터 적용"""
        if projects_df.empty:
            return projects_df
        
        filtered = projects_df.copy()
        
        # 1. 기간 필터
        period_type = st.session_state.get('period_type', '전체')
        date_criteria = st.session_state.get('date_criteria', '납기일')
        
        # 기준 컬럼 선택
        date_criteria = st.session_state.get('date_criteria', '최종납기일')
        if date_criteria == '최종납기일':
            date_col = 'final_due_date'
        else:  # 설치완료일
            date_col = 'installation_completed_date'
        
        if period_type == '년도' and date_col in filtered.columns:
            year = st.session_state.get('filter_year')
            if year:
                filtered = filtered[
                    pd.to_datetime(filtered[date_col], errors='coerce').dt.year == year
                ]
        elif period_type == '월별' and date_col in filtered.columns:
            year = st.session_state.get('filter_year_month')
            month = st.session_state.get('filter_month')
            if year and month:
                filtered = filtered[
                    (pd.to_datetime(filtered[date_col], errors='coerce').dt.year == year) &
                    (pd.to_datetime(filtered[date_col], errors='coerce').dt.month == month)
                ]
        
        # 2. 상태 필터
        status_filter = st.session_state.get('status_filter', '진행중')
        if status_filter != '전체' and 'status' in filtered.columns:
            filtered = filtered[filtered['status'] == status_filter]

        # 3. 관급/사급 필터
        project_type_filter = st.session_state.get('project_type_filter', '전체')
        if project_type_filter != '전체' and 'contract_type' in filtered.columns:
            filtered = filtered[filtered['contract_type'] == project_type_filter]

        return filtered
    
    def render_orders_table_improved(_self, orders_df):
        """발주 현황 테이블 - 스티커 + 관급/사급 수정 가능"""
        if orders_df.empty:
            st.info("📋 발주 데이터가 없습니다.")
            return None
        
        st.subheader("📋 발주 현황")
        
        try:
            # 표시용 데이터프레임 준비
            display_df = orders_df.copy()
            
            # 프로젝트 정보 가져오기 (관급/사급 표시용)
            display_df['관급/사급'] = display_df['project_id'].apply(
                lambda pid: _self.db.get_project_by_id(pid).get('contract_type', '관급') 
                if pid and _self.db.get_project_by_id(pid) is not None else '관급'
            )
            
            # 스티커 공정 상태 확인
            def get_sticker_status(order_id):
                events = _self.db.get_latest_events_by_stage(order_id)
                sticker_events = events[events['stage'] == '스티커']
                
                if sticker_events.empty:
                    return '-'
                else:
                    event = sticker_events.iloc[0]
                    if pd.notna(event['done_date']) or event['progress'] >= 100:
                        return '✅'
                    else:
                        return '⚪'
            
            display_df['스티커'] = display_df['order_id'].apply(get_sticker_status)
            
            # 발주일 포맷팅
            if 'order_date' in display_df.columns:
                display_df['발주일'] = display_df['order_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') 
                    else str(x) if pd.notna(x) else ''
                )
            
            # 납기일 포맷팅
            if 'due_date' in display_df.columns:
                display_df['납기일'] = display_df['due_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime')
                    else str(x) if pd.notna(x) else ''
                )
            
            # 컬럼 선택
            display_columns = [
                'project', 'order_id', 'vendor', '관급/사급', '발주일', '납기일',
                'progress_pct', '스티커', 'current_stage', 'status'
            ]
            
            # 존재하는 컬럼만 선택
            display_columns = [col for col in display_columns if col in display_df.columns]
            display_df = display_df[display_columns]
            
            # 컬럼명 한글화
            display_df = display_df.rename(columns={
                'project': '프로젝트',
                'order_id': '발주번호',
                'vendor': '업체',
                'progress_pct': '진행률(%)',
                'current_stage': '현재단계',
                'status': '상태'
            })
            
            # 프로젝트별로 정렬
            if '프로젝트' in display_df.columns:
                display_df = display_df.sort_values(['프로젝트', '발주일'])
            
            # 편집 가능한 테이블
            edited_df = st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                disabled=['발주번호', '진행률(%)', '현재단계', '프로젝트', '업체', '발주일', '납기일', '스티커'],
                column_config={
                    "진행률(%)": st.column_config.ProgressColumn(
                        "진행률",
                        min_value=0,
                        max_value=100,
                    ),
                    "관급/사급": st.column_config.SelectboxColumn(
                        "관급/사급",
                        options=["관급", "사급"],
                        required=True
                    ),
                    "상태": st.column_config.SelectboxColumn(
                        "상태",
                        options=["진행중", "완료", "보류", "취소"],
                        required=True
                    )
                },
                key="orders_table"
            )
            
            # 저장 버튼
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("💾 변경사항 저장", use_container_width=True):
                    try:
                        # 변경된 관급/사급 업데이트
                        for idx, row in edited_df.iterrows():
                            order_id = row['발주번호']
                            new_contract = row['관급/사급']
                            new_status = row['상태']
                            
                            # 해당 발주의 프로젝트 ID 찾기
                            original_order = orders_df[orders_df['order_id'] == order_id].iloc[0]
                            project_id = original_order['project_id']
                            
                            # 프로젝트의 관급/사급 업데이트
                            with _self.db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE projects SET contract_type = ? WHERE project_id = ?",
                                    (new_contract, project_id)
                                )
                                
                                # 발주 상태도 업데이트
                                cursor.execute(
                                    "UPDATE orders SET status = ? WHERE order_id = ?",
                                    (new_status, order_id)
                                )
                        
                        st.success("✅ 변경사항이 저장되었습니다!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ 저장 실패: {e}")
            
            return edited_df
            
        except Exception as e:
            st.error(f"테이블 렌더링 오류: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None
        
    def update_project_amount(_self, project_id, amount):
        """프로젝트 계약금액 업데이트 - Supabase/SQLite 분기"""
        try:
            if USE_SUPABASE:
                _self.db.supabase.table('projects').update({
                    'contract_amount': amount
                }).eq('project_id', project_id).execute()
                return True
            else:
                with _self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE projects 
                        SET contract_amount = ?
                        WHERE project_id = ?
                    """, (amount, project_id))
                    return True
        except Exception as e:
            import streamlit as st
            st.error(f"금액 업데이트 실패: {e}")
            return False
# ============================================================================
# UI 컴포넌트
# ============================================================================

class WIPInterface:
    """WIP 앱 사용자 인터페이스"""
    
    def __init__(_self, wip_manager):
        _self.wip = wip_manager
        _self.db = wip_manager.db
    
    def render_dashboard_cards(_self, customer_id=None):
        """대시보드 KPI 카드 - 프로젝트 기준"""
        # 프로젝트 통계 계산
        projects_df = _self.wip.get_projects_with_orders(customer_id)
        
        if projects_df.empty:
            total = wip = urgent = completed = 0
        else:
            total = len(projects_df)
            
            # 완료
            completed = len(projects_df[projects_df['status'] == '완료'])
            
            # 진행중 (완료 아닌 것)
            wip = total - completed
            
            # 임박 (D-7 이내, overdue + urgent 합산)
            urgent = len(projects_df[
                (projects_df['warning_level'] == 'overdue') | 
                (projects_df['warning_level'] == 'urgent')
            ])
        
        # 작은 글자로 표시
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div style='text-align: center; padding: 2px; margin: 0;'>
                <p style='font-size: 0.7rem; margin: 0; padding: 0; color: gray;'>총 발주</p>
                <p style='font-size: 1.3rem; margin: 0; padding: 0; font-weight: bold;'>{total}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style='text-align: center; padding: 2px; margin: 0;'>
                <p style='font-size: 0.7rem; margin: 0; padding: 0; color: gray;'>진행중</p>
                <p style='font-size: 1.3rem; margin: 0; padding: 0; font-weight: bold; color: #1f77b4;'>{wip}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style='text-align: center; padding: 2px; margin: 0;'>
                <p style='font-size: 0.7rem; margin: 0; padding: 0; color: gray;'>임박 🟠</p>
                <p style='font-size: 1.3rem; margin: 0; padding: 0; font-weight: bold; color: #ff7f0e;'>{urgent}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div style='text-align: center; padding: 2px; margin: 0;'>
                <p style='font-size: 0.7rem; margin: 0; padding: 0; color: gray;'>완료 ✅</p>
                <p style='font-size: 1.3rem; margin: 0; padding: 0; font-weight: bold; color: #2ca02c;'>{completed}</p>
            </div>
            """, unsafe_allow_html=True)
    
    def render_filters(_self, orders_df):
        """필터 UI"""
        st.subheader("🔍 필터")
        
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        
        with col1:
            projects = ["(전체)"] + sorted(orders_df['project'].dropna().unique().tolist())
            f_project = st.selectbox("프로젝트", projects, key="filter_project")
        
        with col2:
            vendors = ["(전체)"] + sorted(orders_df['vendor'].dropna().unique().tolist())
            f_vendor = st.selectbox("업체", vendors, key="filter_vendor")
        
        with col3:
            f_status = st.selectbox(
                "상태",
                ["(전체)", "진행중", "완료", "지연"],
                key="filter_status"
            )
        
        with col4:
            f_stages = st.multiselect(
                "현재 단계",
                _self.wip.stages,
                key="filter_stages"
            )
        
        return {
            'project': f_project,
            'vendor': f_vendor,
            'status': f_status,
            'stages': f_stages
        }
    
    def apply_filters(_self, orders_df, filters):
        """필터 적용"""
        filtered = orders_df.copy()
        
        if filters['project'] != "(전체)":
            filtered = filtered[filtered['project'] == filters['project']]
        
        if filters['vendor'] != "(전체)":
            filtered = filtered[filtered['vendor'] == filters['vendor']]
        
        today = date.today()
        if filters['status'] == "진행중":
            filtered = filtered[filtered['progress_pct'] < 100]
        elif filters['status'] == "완료":
            filtered = filtered[filtered['progress_pct'] >= 100]
        elif filters['status'] == "지연":
            filtered = filtered[
                (filtered['due_date'].notna()) &
                (filtered['due_date'] < today) &
                (filtered['progress_pct'] < 100)
            ]
        
        if filters['stages']:
            filtered = filtered[filtered['current_stage'].isin(filters['stages'])]
        
        return filtered
    
    def render_orders_table(_self, orders_df):
        """발주 목록 테이블 (편집 가능) - 프로젝트 중심"""
        if orders_df.empty:
            st.info("📋 발주 데이터가 없습니다.")
            return None
        
        st.subheader("📋 발주 현황")
        
        try:
            # ===== 이미 orders_df에 프로젝트 정보가 포함되어 있음 =====
            # orders_with_project 호출 제거!
            
            # 표시용 데이터프레임 준비
            display_df = orders_df.copy()
            
            # 필수 컬럼 확인
            required_cols = ['order_id', 'project', 'vendor', 'progress_pct', 'current_stage', 'status']
            missing_cols = [col for col in required_cols if col not in display_df.columns]
            
            if missing_cols:
                st.error(f"필수 컬럼 누락: {missing_cols}")
                st.write("사용 가능한 컬럼:", list(display_df.columns))
                return None
            
            # 발주일 포맷팅
            if 'order_date' in display_df.columns:
                display_df['발주일'] = display_df['order_date'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') 
                    else str(x) if pd.notna(x) else ''
                )
            else:
                display_df['발주일'] = ''
            
            # 프로젝트 최종 납기 포맷팅
            if 'project_final_due' in display_df.columns:
                display_df['전체납기일'] = display_df['project_final_due'].apply(
                    lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime')
                    else ''
                )
            else:
                display_df['전체납기일'] = ''
            
            # 납기 경고 생성
            def get_warning_icon(row):
                warning = row.get('project_warning', 'normal')
                d_day = row.get('project_d_day', '')
                
                if warning == 'overdue':
                    return f"🔴 {d_day}"
                elif warning == 'urgent':
                    return f"🟠 {d_day}"
                elif warning == 'warning':
                    return f"🟡 {d_day}"
                else:
                    return f"✅ {d_day}"
            
            display_df['납기상태'] = display_df.apply(get_warning_icon, axis=1)
            
            # 컬럼 선택 및 순서
            final_columns = [
                'project', 'order_id', 'vendor', '발주일',
                '전체납기일', '납기상태',
                'progress_pct', 'current_stage', 'status'
            ]
            
            # 존재하는 컬럼만 선택
            final_columns = [col for col in final_columns if col in display_df.columns]
            display_df = display_df[final_columns]
            
            # 컬럼명 최종 매핑
            display_df = display_df.rename(columns={
                'project': '프로젝트',
                'order_id': '발주번호',
                'vendor': '업체',
                'progress_pct': '진행률(%)',
                'current_stage': '현재단계',
                'status': '상태'
            })
            
            # 프로젝트별로 정렬
            if '프로젝트' in display_df.columns and '발주일' in display_df.columns:
                display_df = display_df.sort_values(['프로젝트', '발주일'])
            
            # 편집 가능한 테이블
            st.data_editor(
                display_df,
                use_container_width=True,
                hide_index=True,
                disabled=['발주번호', '진행률(%)', '현재단계', '전체납기일', '납기상태'],
                column_config={
                    "진행률(%)": st.column_config.ProgressColumn(
                        "진행률",
                        min_value=0,
                        max_value=100,
                    ),
                },
                key="orders_table"
            )
            
            return display_df
            
        except Exception as e:
            st.error(f"테이블 렌더링 오류: {e}")
            import traceback
            st.code(traceback.format_exc())
            return None
    
    def render_order_detail(_self, order_id):
        """발주 상세 정보 및 진행 업데이트"""
        order = _self.db.get_order_by_id(order_id)
        if order is None:
            st.error("발주를 찾을 수 없습니다.")
            return
        
        # 진행률 정보
        progress_info = _self.wip.calculate_order_progress(order_id)
        
        # 헤더
        st.subheader(f"🗂️ {order['project']} - {order['vendor']}")
        st.caption(f"발주번호: {order['order_id']}")
        
        # 기본 정보
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("진행률", f"{progress_info['progress_pct']}%")
        
        with col2:
            due_str = order['due_date'].strftime('%Y-%m-%d') if pd.notna(order['due_date']) else "미정"
            st.metric("납기일", due_str)
        
        with col3:
            st.metric("현재 단계", progress_info['current_stage'])
        
        # 진행률 바
        st.progress(progress_info['progress_pct'] / 100)
        
        # 단계별 현황
        st.markdown("**단계별 현황**")
        stage_chips = _self.wip.format_stage_chips(progress_info['stage_status'])
        st.markdown(stage_chips)
        
        st.markdown("---")
        
        # 진행 상황 업데이트 폼
        st.markdown("### 🔧 진행 상황 업데이트")
        
        with st.form(key=f"update_form_{order_id}"):
            col1, col2 = st.columns(2)
            
            with col1:
                stage = st.selectbox("단계", _self.wip.stages)
                progress = st.slider("진행률 (%)", 0, 100, 100, 5)
            
            with col2:
                done_date = st.date_input("완료일", value=date.today())
                note = st.text_input("메모", placeholder="작업 내용...")
            
            submitted = st.form_submit_button("📝 업데이트 등록", use_container_width=True)
            
            if submitted:
                try:
                    _self.db.add_process_event(
                        order_id=order_id,
                        stage=stage,
                        progress=progress,
                        done_date=done_date if progress >= 100 else None,
                        note=note
                    )
                    st.success("✅ 진행 상황이 업데이트되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 오류: {e}")
        
        # 최근 이벤트 이력
        st.markdown("---")
        st.markdown("### 📜 최근 진행 이력")
        
        events = _self.db.get_process_events(order_id)
        if not events.empty:
            for _, event in events.head(10).iterrows():
                created = pd.to_datetime(event['created_at']).strftime('%Y-%m-%d %H:%M')
                done = event['done_date'].strftime('%Y-%m-%d') if pd.notna(event['done_date']) else '진행중'
                
                st.write(f"**{event['stage']}** - {event['progress']}% | 완료: {done} | 등록: {created}")
                if event['note']:
                    st.caption(f"메모: {event['note']}")
                st.divider()
        else:
            st.info("아직 진행 이력이 없습니다.")
    
    def render_delete_order_button(_self, order_id):
        """발주 삭제 버튼"""
        if st.button("🗑️ 이 발주 삭제", type="secondary", key=f"delete_{order_id}"):
            if st.session_state.get(f'confirm_delete_{order_id}'):
                try:
                    _self.db.delete_order(order_id)
                    st.success(f"✅ 발주 '{order_id}'가 삭제되었습니다!")
                    st.session_state[f'confirm_delete_{order_id}'] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 삭제 실패: {e}")
            else:
                st.session_state[f'confirm_delete_{order_id}'] = True
                st.warning("⚠️ 한 번 더 클릭하면 삭제됩니다. 삭제된 데이터는 복구할 수 없습니다!")
                st.rerun()    

    def filter_by_project_status(_self, orders_df, show_completed=False):
        """완료된 프로젝트 필터링"""
        if orders_df.empty:
            return orders_df
        
        if not show_completed:
            # 진행률 100% 미만만 표시
            orders_df = orders_df[orders_df['progress_pct'] < 100]
        
        return orders_df
    
    def render_project_summary_table(_self, customer_id=None):
        """프로젝트 요약 테이블 (편집 가능)"""
        st.subheader("📊 프로젝트 요약")
        
        projects_df = _self.wip.get_projects_with_orders(customer_id)
        
        if projects_df.empty:
            st.info("📋 프로젝트가 없습니다.")
            return
        
        # 표시용 데이터프레임 준비
        display_df = projects_df.copy()
        
        # 납기일 포맷팅
        display_df['최종납기일'] = display_df['final_due_date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
        )
        
        # 설치완료일 포맷팅
        display_df['설치완료일'] = display_df['installation_completed_date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') else ''
        )
        
        # 납기 상태 아이콘
        def get_status_icon(row):
            if row['warning_level'] == 'overdue':
                return f"🔴 {row['d_day']}"
            elif row['warning_level'] == 'urgent':
                return f"🟠 {row['d_day']}"
            elif row['warning_level'] == 'warning':
                return f"🟡 {row['d_day']}"
            else:
                return f"✅ {row['d_day']}"
        
        display_df['납기상태'] = display_df.apply(get_status_icon, axis=1)
        
        # 서류 발행 상태
        display_df['세금계산서'] = display_df['tax_invoice_issued'].apply(lambda x: '✅' if x else '⚪')
        display_df['거래명세서'] = display_df['trade_statement_issued'].apply(lambda x: '✅' if x else '⚪')
        
        # 인원/일수 처리
        display_df['인원'] = display_df['installation_staff_count'].apply(
            lambda x: f"{int(x)}명" if pd.notna(x) else ''
        )
        display_df['일수'] = display_df['installation_days'].apply(
            lambda x: f"{int(x)}일" if pd.notna(x) else ''
        )
        
        # 컬럼 선택
        final_columns = [
            'project_name', 'contract_type', '최종납기일', '납기상태',
            '설치완료일', '인원', '일수', '세금계산서', '거래명세서',
            'order_count', 'total_progress'
        ]
        
        display_df = display_df[final_columns]
        
        # 컬럼명 한글화
        display_df = display_df.rename(columns={
            'project_name': '프로젝트',
            'contract_type': '관급/사급',
            'order_count': '발주건수',
            'total_progress': '전체진행률(%)'
        })
        
        # 편집 가능한 테이블
        st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            disabled=['프로젝트', '관급/사급', '최종납기일', '납기상태', '발주건수', '전체진행률(%)'],
            column_config={
                "전체진행률(%)": st.column_config.ProgressColumn(
                    "전체진행률",
                    min_value=0,
                    max_value=100,
                ),
                "설치완료일": st.column_config.DateColumn(
                    "설치완료일",
                    format="YYYY-MM-DD"
                ),
            },
            key="project_summary_table"
        )
        
        st.caption("💡 설치완료일, 인원, 일수는 직접 수정할 수 있습니다. (현재는 표시만 가능, 저장 기능은 다음 단계에서 구현)")
        
        return projects_df
    
    def render_order_detail_by_project(_self, project_id, project_name):
        """프로젝트별 발주 상세 현황 (공정별 컬럼 형태)"""
        
        # 해당 프로젝트의 모든 발주
        orders = _self.db.get_orders()
        project_orders = orders[orders['project_id'] == project_id]
        
        if project_orders.empty:
            st.info(f"'{project_name}' 프로젝트에 발주 내역이 없습니다.")
            return
        
        # 공정 목록
        stages = ['절단/절곡', 'P레이저', '레이저(판재)', '벤딩', '페인트', '스티커', '입고']
        
        # 프로젝트별 공정 현황 (1행으로 표시)
        row_data = {'프로젝트': project_name}
        
        # 공정별 상태를 dict로 저장 (버튼 생성용)
        stage_buttons = {}
        
        for stage in stages:
            # 해당 공정의 발주 찾기
            stage_orders = []
            stage_data = []  # 버튼 생성용 데이터

            for _, order in project_orders.iterrows():
                # order_id에서 공정 타입 추출 (예: ORD-고덕초01-BAND-01 → BAND)
                order_parts = order['order_id'].split('-')
                if len(order_parts) < 3:
                    continue
                
                process_type = order_parts[2]
                
                process_map = {
                    'CUT': '절단/절곡',
                    'PLASER': 'P레이저',
                    'LASER': '레이저(판재)',
                    'BAND': '벤딩',
                    'PAINT': '페인트',
                    'STICKER': '스티커',
                    'RECEIVING': '입고'
                }
                
                target_stage = process_map.get(process_type)
                
                # 현재 순회 중인 공정과 일치하지 않으면 스킵
                if target_stage != stage:
                    continue
                
                events = _self.db.get_latest_events_by_stage(order['order_id'])
                
                # 이벤트가 없으면 자동 생성
                if events.empty:
                    vendor = order.get('vendor', '미정')
                    try:
                        _self.db.add_process_event(
                            order_id=order['order_id'],
                            stage=stage,
                            progress=0,
                            done_date=None,
                            vendor=vendor,
                            note='기존 발주 마이그레이션'
                        )
                        # 다시 조회
                        events = _self.db.get_latest_events_by_stage(order['order_id'])
                    except Exception as e:
                        print(f"이벤트 생성 실패: {e}")
                        continue
                
                # 여전히 비어있으면 스킵
                if events.empty:
                    continue
                
                # 'stage' 또는 'process_stage' 컬럼명 확인
                if 'stage' in events.columns:
                    stage_events = events[events['stage'] == stage]
                elif 'process_stage' in events.columns:
                    stage_events = events[events['process_stage'] == stage]
                else:
                    print(f"[WARNING] 공정 컬럼을 찾을 수 없습니다. 사용 가능한 컬럼: {events.columns.tolist()}")
                    continue
                
                if not stage_events.empty:
                    event = stage_events.iloc[0]
                    vendor = event.get('vendor', order['vendor'])
                    is_done = pd.notna(event['done_date']) or event['progress'] >= 100
                    
                    if is_done:
                        stage_orders.append(f"✅ {vendor}")
                    else:
                        stage_orders.append(f"⚪ {vendor}")
                    
                    # 버튼용 데이터 저장
                    stage_data.append({
                        'vendor': vendor,
                        'order_id': order['order_id'],
                        'is_done': is_done,
                        'event_id': event['event_id']
                    })
            
            # 공정별 표시
            if stage_orders:
                row_data[stage] = " | ".join(stage_orders)
                stage_buttons[stage] = stage_data
            else:
                row_data[stage] = "-"
                stage_buttons[stage] = []
        
        # 데이터프레임 생성
        detail_df = pd.DataFrame([row_data])
        
        # 테이블 표시
        st.dataframe(
            detail_df,
            use_container_width=True,
            hide_index=True
        )
        
        st.caption("✅ 완료 | ⚪ 진행중/대기 | - 해당없음")

        # 업체 변경 및 완료 처리 UI
        st.markdown("---")

        with st.expander("🔧 업체 변경 및 완료 처리", expanded=False):
            for stage, data_list in stage_buttons.items():
                if data_list:
                    for idx, data in enumerate(data_list):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        with col1:
                            st.caption(f"**{stage}**")
                        
                        with col2:
                            # 해당 공정 업체 목록
                            vendors_df = _self.db.get_vendors(stage)
                            
                            if not vendors_df.empty:
                                vendor_options = vendors_df['vendor_name'].tolist()
                                # 현재 업체가 목록에 없으면 추가
                                if data['vendor'] not in vendor_options:
                                    vendor_options.insert(0, data['vendor'])
                                
                                current_index = vendor_options.index(data['vendor']) if data['vendor'] in vendor_options else 0
                                
                                new_vendor = st.selectbox(
                                    "업체",
                                    vendor_options,
                                    index=current_index,
                                    key=f"vendor_select_{project_id}_{stage}_{idx}",
                                    label_visibility="collapsed"
                                )
                            else:
                                new_vendor = data['vendor']
                                st.text(data['vendor'])
                        
                        with col3:
                            # 완료 상태 토글 버튼
                            if st.button(
                                "✅" if data['is_done'] else "⚪",
                                key=f"status_btn_{project_id}_{stage}_{idx}",
                                use_container_width=True,
                                help="완료 상태 토글"
                            ):
                                # 상태 토글 (반대로)
                                from datetime import date as date_module
                                new_status = not data['is_done']  # 현재 상태의 반대
                                
                                _self.db.add_process_event(
                                    order_id=data['order_id'],
                                    stage=stage,
                                    progress=100 if new_status else 0,
                                    done_date=date_module.today() if new_status else None,
                                    vendor=new_vendor,
                                    note=f"상태 변경: {'완료' if new_status else '진행중'}"
                                )
                                # ✅ 캐시 초기화 추가 (즉시 반영)
                                try:
                                    _self.db.get_process_events.clear()
                                    _self.db.get_latest_events_by_stage.clear()
                                    _self.db.get_orders.clear()
                                    _self.wip.get_orders_with_progress.clear()
                                    _self.wip.get_dashboard_stats.clear()
                                    _self.wip.get_projects_with_orders.clear()
                                except Exception:
                                    pass
                                st.rerun()
                    
                    st.divider()
        

    def render_project_installation_table(_self, project_id, project):
        """프로젝트 설치 정보 편집 테이블 (인라인) - 관급/사급 구분"""
        
        # 현재 값 가져오기 - Series가 아닌 scalar 값으로 변환
        install_date = project.get('installation_completed_date')
        
        # Series인 경우 첫 번째 값 추출
        if isinstance(install_date, pd.Series):
            install_date = install_date.iloc[0] if not install_date.empty else None
        
        # 날짜 변환
        if pd.notna(install_date) and install_date != '':
            if isinstance(install_date, str):
                try:
                    install_date = pd.to_datetime(install_date).date()
                except:
                    install_date = None
            elif hasattr(install_date, 'date'):
                install_date = install_date.date() if callable(install_date.date) else install_date
            elif not isinstance(install_date, date):
                install_date = None
        else:
            install_date = None
        
        # 인원/일수 처리
        staff_count = project.get('installation_staff_count')
        if isinstance(staff_count, pd.Series):
            staff_count = staff_count.iloc[0] if not staff_count.empty else 0
        staff_count = int(staff_count) if pd.notna(staff_count) else 0
        
        install_days = project.get('installation_days')
        if isinstance(install_days, pd.Series):
            install_days = install_days.iloc[0] if not install_days.empty else 0
        install_days = int(install_days) if pd.notna(install_days) else 0
        
        # 체크박스 처리
        tax_invoice = project.get('tax_invoice_issued', False)
        if isinstance(tax_invoice, pd.Series):
            tax_invoice = tax_invoice.iloc[0] if not tax_invoice.empty else False
        tax_invoice = bool(tax_invoice)
        
        trade_statement = project.get('trade_statement_issued', False)
        if isinstance(trade_statement, pd.Series):
            trade_statement = trade_statement.iloc[0] if not trade_statement.empty else False
        trade_statement = bool(trade_statement)
        
        contract_type = project.get('contract_type', '관급')
        if isinstance(contract_type, pd.Series):
            contract_type = contract_type.iloc[0] if not contract_type.empty else '관급'
        
        # 관급/사급에 따라 데이터프레임 다르게 생성
        if contract_type == '관급':
            # 관급: 서류 발행 컬럼 없음
            data = {
                '설치완료일': [install_date if install_date else None],
                '투입인원': [staff_count if staff_count > 0 else 0],
                '설치일수': [install_days if install_days > 0 else 0]
            }
        else:
            # 사급: 서류 발행 컬럼 포함
            data = {
                '설치완료일': [install_date if install_date else None],
                '투입인원': [staff_count if staff_count > 0 else 0],
                '설치일수': [install_days if install_days > 0 else 0],
                '세금계산서': [tax_invoice],
                '거래명세서': [trade_statement]
            }
        
        df = pd.DataFrame(data)
        
        # 편집 가능한 테이블
        column_config = {
            "설치완료일": st.column_config.DateColumn(
                "설치완료일",
                format="YYYY-MM-DD"
            ),
            "투입인원": st.column_config.NumberColumn(
                "투입인원",
                min_value=0,
                max_value=50,
                step=1,
                format="%d명"
            ),
            "설치일수": st.column_config.NumberColumn(
                "설치일수",
                min_value=0,
                max_value=365,
                step=1,
                format="%d일"
            )
        }
        
        # 사급이면 체크박스 컬럼 추가
        if contract_type == '사급':
            column_config["세금계산서"] = st.column_config.CheckboxColumn("세금계산서")
            column_config["거래명세서"] = st.column_config.CheckboxColumn("거래명세서")
        
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config=column_config,
            key=f"install_table_{project_id}"
        )
        
        # 저장된 데이터를 세션에 저장 (저장 버튼에서 사용)
        st.session_state[f'edited_data_{project_id}'] = {
            'date': edited_df['설치완료일'].iloc[0],
            'staff': int(edited_df['투입인원'].iloc[0]),
            'days': int(edited_df['설치일수'].iloc[0]),
            'tax': bool(edited_df['세금계산서'].iloc[0]) if contract_type == '사급' else False,
            'trade': bool(edited_df['거래명세서'].iloc[0]) if contract_type == '사급' else False,
            'contract_type': contract_type
        }
    
    def render_project_summary_with_toggle(_self, customer_id=None):
        """프로젝트 요약 + 토글 발주 상세 통합 (컴팩트)"""
        st.markdown("#### 📊 프로젝트 현황")
        
        projects_df = _self.wip.get_projects_with_orders(customer_id)
        
        # 필터 적용
        if not projects_df.empty:
            projects_df = _self.wip.apply_filters_to_projects(projects_df)
        
        if projects_df.empty:
            st.info("📋 프로젝트가 없습니다.")
            return
        
        # 프로젝트별로 렌더링
        for idx, project in projects_df.iterrows():
            # 프로젝트 헤더 (컴팩트)
            col1, col2, col3, col4, col5 = st.columns([3, 1.2, 1.2, 0.8, 0.8])
            
            with col1:
                # 프로젝트명 + 납기상태
                status_icon = ""
                if project['warning_level'] == 'overdue':
                    status_icon = f"🔴 {project['d_day']}"
                elif project['warning_level'] == 'urgent':
                    status_icon = f"🟠 {project['d_day']}"
                elif project['warning_level'] == 'warning':
                    status_icon = f"🟡 {project['d_day']}"
                else:
                    status_icon = f"✅ {project['d_day']}"
                
                st.markdown(f"**{project['project_name']}** {status_icon}")
            
            with col2:
                due_date = project['final_due_date'].strftime('%m/%d') if pd.notna(project['final_due_date']) else '-'
                st.caption(f"📅 {due_date} | {project['contract_type']}")
            
            with col3:
                st.caption(f"📦 {project['order_count']}건")
            
            with col4:
                progress_bar = "🟩" * (project['total_progress'] // 20) + "⬜" * (5 - project['total_progress'] // 20)
                st.caption(f"{progress_bar} {project['total_progress']}%")
            
            with col5:
                # 저장 버튼
                if st.button("💾", key=f"save_{project['project_id']}", help="설치정보 저장"):
                    try:
                        edited_data = st.session_state.get(f"edited_data_{project['project_id']}")
                        
                        if edited_data:
                            # 설치 정보 업데이트
                            _self.wip.update_project_installation(
                                project['project_id'],
                                completed_date=edited_data['date'] if pd.notna(edited_data['date']) else None,
                                staff_count=edited_data['staff'] if edited_data['staff'] > 0 else None,
                                days=edited_data['days'] if edited_data['days'] > 0 else None  # ✅ install_days → days
                            )
                            
                            # 사급인 경우 서류 발행 정보 업데이트
                            if edited_data['contract_type'] == '사급':
                                _self.wip.update_project_documents(
                                    project['project_id'],
                                    tax_invoice=edited_data['tax'],
                                    trade_statement=edited_data['trade']
                                )
                            
                            # 프로젝트 상태 자동 업데이트
                            _self.wip.auto_update_project_status(project['project_id'])
                            
                            # ✅ 캐시 초기화 추가
                            try:
                                _self.db.get_projects.clear()
                                _self.wip.get_projects_with_orders.clear()
                                _self.wip.get_dashboard_stats.clear()
                            except Exception:
                                pass
                           
                            st.success("✅ 저장!")
                            st.rerun()
                        else:
                            st.warning("수정된 데이터가 없습니다.")
             
                    except Exception as e:
                        st.error(f"❌ 저장 실패: {e}")
                        import traceback
                        st.code(traceback.format_exc())
            
            # 설치 정보 (있으면 표시 - 한 줄로 압축)
            if pd.notna(project.get('installation_completed_date')):
                install_info = []
                
                install_date_val = project.get('installation_completed_date')
                if pd.notna(install_date_val) and install_date_val != '':
                    if isinstance(install_date_val, str):
                        completed = install_date_val[:5] if len(install_date_val) >= 10 else install_date_val  # YYYY-MM-DD에서 MM/DD 추출
                    elif hasattr(install_date_val, 'strftime'):
                        completed = install_date_val.strftime('%m/%d')
                    else:
                        completed = str(install_date_val)
                else:
                    completed = ''
                install_info.append(f"✅설치: {completed}")
                
                staff = project.get('installation_staff_count')
                if pd.notna(staff):
                    install_info.append(f"👷{int(staff)}명")
                
                days = project.get('installation_days')
                if pd.notna(days):
                    install_info.append(f"📅{int(days)}일")
                
                if project.get('tax_invoice_issued'):
                    install_info.append("📄계산서")
                if project.get('trade_statement_issued'):
                    install_info.append("📋명세서")
                
                st.caption(" | ".join(install_info))
            
            # 설치정보 편집 테이블
            project_obj = _self.db.get_project_by_id(project['project_id'])
            if project_obj is not None:
                _self.render_project_installation_table(project['project_id'], project_obj)
            
            # 발주 상세는 토글로
            with st.expander(f"🔍 '{project['project_name']}' 발주 상세보기", expanded=False):
                _self.render_order_detail_by_project(project['project_id'], project['project_name'])

            st.markdown("---")

    def render_project_summary_table_simple(_self, customer_id=None):
        """프로젝트 요약 테이블 - 한눈에 보기"""
        
        projects_df = _self.wip.get_projects_with_orders(customer_id)
        
        # 필터 적용
        if not projects_df.empty:
            projects_df = _self.wip.apply_filters_to_projects(projects_df)
        
        if projects_df.empty:
            st.info("📋 프로젝트가 없습니다.")
            
            # 신규 프로젝트 생성 버튼
            if st.button("➕ 신규 프로젝트 생성", use_container_width=True):
                _self.show_new_project_modal()
            return
        
        # 표시용 데이터 준비
        display_data = []
        
        for _, project in projects_df.iterrows():
            # 납기 상태
            warning_level = project['warning_level']
            d_day = project['d_day']
            
            if warning_level == 'overdue':
                status_icon = f"🔴 {d_day}"
            elif warning_level == 'urgent':
                status_icon = f"🟠 {d_day}"
            elif warning_level == 'warning':
                status_icon = f"🟡 {d_day}"
            else:
                status_icon = f"✅ {d_day}"
            
            # 설치 정보
            install_date = project.get('installation_completed_date')
            if pd.notna(install_date) and install_date != '':
                if isinstance(install_date, str):
                    install_date_str = install_date
                elif hasattr(install_date, 'strftime'):
                    install_date_str = install_date.strftime('%Y-%m-%d')
                else:
                    install_date_str = str(install_date)
            else:
                install_date_str = ''
            
            staff = project.get('installation_staff_count')
            staff_str = f"{int(staff)}명" if pd.notna(staff) else ''
            
            days = project.get('installation_days')
            days_str = f"{int(days)}일" if pd.notna(days) else ''
            
            display_data.append({
                '프로젝트명': project['project_name'],
                '관급/사급': project.get('contract_type', '관급'),
                '최종납기일': project['final_due_date'].strftime('%Y-%m-%d') if pd.notna(project['final_due_date']) else '',
                '납기상태': status_icon,
                '발주건수': f"{project['order_count']}건",
                '진행률': project['total_progress'],
                '설치완료일': install_date_str,
                '인원': staff_str,
                '일수': days_str,
                '상태': project['status']
            })
        
        summary_df = pd.DataFrame(display_data)
        
        # 테이블 표시
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "진행률": st.column_config.ProgressColumn(
                    "진행률(%)",
                    min_value=0,
                    max_value=100,
                ),
            }
        )
        
        # 신규 프로젝트 생성 및 삭제 버튼
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("➕ 신규 프로젝트", use_container_width=True):
                _self.show_new_project_modal()
        
        with col2:
            # 프로젝트 삭제
            if not projects_df.empty:
                project_names = projects_df['project_name'].tolist()
                selected_to_delete = st.selectbox(
                    "삭제할 프로젝트",
                    ["선택..."] + project_names,
                    key="delete_project_select"
                )
                
                if selected_to_delete != "선택...":
                    if st.button("🗑️ 삭제", use_container_width=True, type="secondary"):
                        # 프로젝트 ID 찾기
                        project_to_delete = projects_df[projects_df['project_name'] == selected_to_delete].iloc[0]
                        project_id = project_to_delete['project_id']
                        
                        try:
                            if USE_SUPABASE:
                                # 1. 연관된 발주의 이벤트 먼저 삭제
                                orders_response = _self.db.supabase.table('orders').select('order_id').eq('project_id', project_id).execute()
                                for order in orders_response.data:
                                    _self.db.supabase.table('process_events').delete().eq('order_id', order['order_id']).execute()
                                
                                # 2. 연관된 발주 삭제
                                _self.db.supabase.table('orders').delete().eq('project_id', project_id).execute()
                                
                                # 3. 프로젝트 삭제
                                _self.db.supabase.table('projects').delete().eq('project_id', project_id).execute()
                            else:
                                with _self.db.get_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))

                            # ✅ 캐시 초기화 추가
                            try:
                                _self.db.get_projects.clear()
                                _self.db.get_orders.clear()
                                _self.db.get_process_events.clear()
                                _self.wip.get_projects_with_orders.clear()
                            except Exception:
                                pass
                            
                            st.success(f"프로젝트 '{selected_to_delete}' 삭제 완료!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")
        
        st.markdown("---")
        
        # 프로젝트 데이터 가져오기
        projects_df = _self.wip.get_projects_with_orders(customer_id)
        
        if projects_df.empty:
            st.info("등록된 프로젝트가 없습니다. 신규 프로젝트를 생성해주세요.")
            return
        
        # 필터 적용
        filtered_df = _self.wip.apply_filters_to_projects(projects_df)
        
        if filtered_df.empty:
            st.warning("필터 조건에 맞는 프로젝트가 없습니다.")
            return
        
        # 프로젝트 금액 수정 UI
        st.subheader("💰 계약금액 수정")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            project_to_update = st.selectbox(
                "프로젝트 선택",
                options=filtered_df['project_id'].tolist(),
                format_func=lambda x: f"{x} - {filtered_df[filtered_df['project_id']==x]['project_name'].values[0]}"
            )
        
        with col2:
            current_amount = filtered_df[filtered_df['project_id']==project_to_update]['contract_amount'].values[0]
            new_amount = st.number_input(
                "새 계약금액 (원)",
                min_value=0,
                value=int(current_amount) if pd.notna(current_amount) else 0,
                step=100000
            )
        
        with col3:
            st.write("")  # 정렬용
            st.write("")  # 정렬용
            if st.button("💾 금액 수정", use_container_width=True):
                if _self.wip.update_project_amount(project_to_update, new_amount):
                    # ✅ 캐시 초기화 추가
                    try:
                        _self.db.get_projects.clear()
                        _self.wip.get_projects_with_orders.clear()
                        _self.db.get_top_projects_by_amount.clear()
                    except Exception:
                        pass

                    st.success("✅ 계약금액이 수정되었습니다!")
                    st.rerun()

    @st.dialog("신규 프로젝트 생성")
    def show_new_project_modal(_self):
        """신규 프로젝트 생성 모달"""

        # tenant_id 확인 후 고객사 자동 설정
        tenant_id = st.session_state.get('tenant_id')

        if tenant_id:
            # tenant_id가 있으면 자동으로 설정 (드롭다운 없음)
            customer_id = tenant_id.upper()  # 'dooho' -> 'DOOHO'
            company_name_map = {
                'DOOHO': '두호',
                'KUKJE': '국제'
            }
            st.info(f"**회사:** {company_name_map.get(customer_id, customer_id)}")
        else:
            # tenant_id가 없으면 기존 방식 (고객사 선택)
            customers = _self.db.get_customers()
            if customers.empty:
                st.warning("등록된 고객사가 없습니다.")
                customer_id = st.text_input("고객사 ID", "DOOHO", key="modal_customer_id")
                customer_name = st.text_input("고객사명", "두호", key="modal_customer_name")

                # 임시 고객사 생성
                if st.button("고객사 먼저 생성", key="create_customer_first"):
                    try:
                        _self.db.add_customer(customer_id, customer_name, "")
                        st.success(f"고객사 '{customer_name}' 생성 완료!")
                        # ✅ 캐시 초기화 추가
                        try:
                            _self.db.get_customers.clear()
                        except Exception:
                            pass
                        st.rerun()
                    except Exception as e:
                        st.error(f"고객사 생성 실패: {e}")
            else:
                customer_options = customers['customer_id'].tolist()
                customer_id = st.selectbox("고객사 *", customer_options, key="modal_customer")
        
        # 프로젝트 정보
        project_name = st.text_input("프로젝트명 *", placeholder="시흥초등학교", key="modal_project_name")
        
        col1, col2 = st.columns(2)
        with col1:
            final_due_date = st.date_input(
                "최종 납기일 *", 
                value=date.today() + timedelta(days=30),
                key="modal_due_date"
            )
    
            # ✅ 납품요구일 추가
            delivery_request_date = st.date_input(
                "납품요구일",
                value=date.today() + timedelta(days=25),  # 최종납기 5일 전
                key="modal_delivery_date",
                help="고객사 납품 요구일"
            )
        
        with col2:
            contract_type = st.selectbox("계약 구분 *", ["관급", "사급"], key="modal_contract_type")
            contract_amount = st.number_input(
                "계약금액 (원)",
                min_value=0,
                value=0,
                step=100000,
                help="계약금액을 입력하세요",
                key="modal_contract_amount"
            )

        memo = st.text_area("메모", placeholder="프로젝트 설명...", key="modal_memo")
        
        # 저장 버튼
        col_cancel, col_save = st.columns(2)
        
        with col_cancel:
            if st.button("취소", use_container_width=True, key="modal_cancel"):
                st.rerun()
        
        with col_save:
            if st.button("✅ 생성", use_container_width=True, type="primary", key="modal_save"):
                if not project_name:
                    st.error("프로젝트명을 입력해주세요.")
                else:
                    try:
                        import re
                        
                        # 프로젝트 ID 생성
                        korean_initials = "".join([c for c in project_name if '가' <= c <= '힣'])
                        if korean_initials:
                            initial = korean_initials[:3]
                        else:
                            initial = re.sub(r'[^A-Z0-9]', '', project_name[:4].upper())
                        
                        # 중복 방지
                        existing_projects = _self.db.get_projects(customer_id)
                        counter = 1
                        while True:
                            proj_id = f"PRJ-{initial}{counter:02d}"
                            if existing_projects.empty or proj_id not in existing_projects['project_id'].values:
                                break
                            counter += 1
                        
                        # 프로젝트 생성
                        _self.db.add_project(
                            proj_id,
                            project_name,
                            customer_id,
                            final_due_date,
                            status="진행중",
                            memo=memo,
                            contract_type=contract_type,
                            contract_amount=contract_amount
                        )

                        # ✅ 납품요구일 추가 저장
                        if USE_SUPABASE:
                            _self.db.supabase.table('projects').update({
                                'delivery_request_date': str(delivery_request_date)
                            }).eq('project_id', proj_id).execute()

                        # 관급/사급 및 계약금액 업데이트
                        if USE_SUPABASE:
                            # Supabase 모드
                            _self.db.supabase.table('projects').update({
                                'contract_type': contract_type,
                                'contract_amount': contract_amount
                            }).eq('project_id', proj_id).execute()
                        else:
                            # SQLite 모드
                            with _self.db.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "UPDATE projects SET contract_type = ?, contract_amount = ? WHERE project_id = ?",
                                    (contract_type, contract_amount, proj_id)
                                )
                        
                        # v0.5: 공정별 기본 발주 자동 생성
                        process_list = [
                            ("절단", "절단/절곡"),
                            ("P레이저", "P레이저"),
                            ("레이저", "레이저(판재)"),
                            ("벤딩", "벤딩"),
                            ("도장", "페인트"),
                            ("스티커", "스티커"),
                            ("입고", "입고")
                        ]

                        # 공정명 매핑
                        process_map = {
                            "절단": "CUT",
                            "P레이저": "PLASER",
                            "레이저": "LASER",
                            "벤딩": "BAND",
                            "도장": "PAINT",
                            "스티커": "STICKER",
                            "입고": "RECEIVING"
                        }

                        # 공정별 기본 업체 매핑
                        default_vendor_map = {
                            '절단/절곡': '효성',
                            'P레이저': '화성공장',
                            '레이저(판재)': '두손레이저',
                            '벤딩': '오성벤딩',
                            '페인트': '현대도장',
                            '스티커': '이노텍',
                            '입고': '준비완료'
                        }

                        for process_short, process_full in process_list:
                            # 공정별 기본 업체 선택
                            default_vendor = default_vendor_map.get(process_full, '작업없음')
                            
                            # 발주 ID 생성
                            order_id = _self.db.generate_order_id(proj_id, process_map[process_short])
                            
                            if order_id:
                                try:
                                    # ✅ add_order 메서드 사용 (이미 분기 처리됨)
                                    _self.db.add_order(
                                        order_id=order_id,
                                        customer_id=customer_id,
                                        project_id=proj_id,
                                        project=project_name,
                                        vendor=default_vendor,
                                        order_date=None,
                                        due_date=None,
                                        status='대기',
                                        memo=f'{process_full} 공정'
                                    )
                                    
                                    # 공정 이벤트 추가 (대기 상태)
                                    _self.db.add_process_event(
                                        order_id=order_id,
                                        stage=process_full,
                                        progress=0,
                                        done_date=None,
                                        vendor=default_vendor,
                                        note='프로젝트 생성 시 자동 생성'
                                    )
                                except Exception as e:
                                    print(f"기본 발주 생성 실패 ({process_short}): {e}")

                        st.success(f"프로젝트 '{project_name}' 생성 완료!")
                        st.success(f"✅ 공정별 기본 발주 {len(process_list)}건이 자동 생성되었습니다!")

                        # ✅ 캐시 초기화 추가
                        try:
                            _self.db.get_project_by_id.clear()
                            _self.db.get_projects.clear()
                            _self.db.get_orders.clear()
                            _self.db.get_process_events.clear()
                            _self.wip.get_projects_with_orders.clear()
                            _self.wip.get_dashboard_stats.clear()
                        except Exception:
                            pass

                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"생성 실패: {e}")
                        import traceback
                        st.code(traceback.format_exc())                
                        
    @st.dialog("프로젝트 수정")
    def show_edit_project_modal(_self, project_id):
        """프로젝트 정보 수정 모달"""
        
        # 프로젝트 정보 가져오기
        project = _self.db.get_project_by_id(project_id)
        if project is None:
            st.error("프로젝트를 찾을 수 없습니다.")
            return
        
        st.caption(f"프로젝트 ID: {project_id}")
        
        # 수정 폼
        col1, col2 = st.columns(2)

        with col1:
            contract_type = st.selectbox(
                "관급/사급 *",
                ["관급", "사급"],
                index=0 if project.get('contract_type', '관급') == '관급' else 1,
                key=f"edit_contract_{project_id}"
            )
            
            final_due_date = st.date_input(
                "최종 납기일 *",
                value=project['final_due_date'] if pd.notna(project.get('final_due_date')) else date.today(),
                key=f"edit_due_{project_id}"
            )
            
            contract_amount = st.number_input(
                "계약금액 (원)",
                min_value=0,
                value=int(project.get('contract_amount', 0)) if pd.notna(project.get('contract_amount')) else 0,
                step=100000,
                key=f"edit_amount_{project_id}"
            )
        
        with col2:
            install_date = st.date_input(
                "설치완료일",
                value=project.get('installation_completed_date') if pd.notna(project.get('installation_completed_date')) else None,
                key=f"edit_install_{project_id}"
            )
            
            col_staff, col_days = st.columns(2)
            with col_staff:
                staff_count = st.number_input(
                    "투입인원",
                    min_value=0,
                    max_value=50,
                    value=int(project.get('installation_staff_count', 0)) if pd.notna(project.get('installation_staff_count')) else 0,
                    key=f"edit_staff_{project_id}"
                )
            
            with col_days:
                install_days = st.number_input(
                    "설치일수",
                    min_value=0,
                    max_value=365,
                    value=int(project.get('installation_days', 0)) if pd.notna(project.get('installation_days')) else 0,
                    key=f"edit_days_{project_id}"
                )
        
        # 버튼
        col_cancel, col_save = st.columns(2)
        
        with col_cancel:
            if st.button("취소", use_container_width=True, key=f"edit_cancel_{project_id}"):
                st.rerun()
        
        with col_save:
            if st.button("💾 저장", use_container_width=True, type="primary", key=f"edit_save_{project_id}"):
                try:
                    # 프로젝트 정보 업데이트
                    with _self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE projects 
                            SET contract_type = ?,
                                final_due_date = ?,
                                installation_completed_date = ?,
                                installation_staff_count = ?,
                                installation_days = ?
                            WHERE project_id = ?
                        """, (
                            contract_type,
                            final_due_date,
                            install_date if install_date else None,
                            staff_count if staff_count > 0 else None,
                            install_days if install_days > 0 else None,
                            project_id
                        ))
                    
                    st.success("프로젝트 정보가 수정되었습니다!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    @st.dialog("업체 정보 수정")
    def show_edit_vendor_modal(_self, order_id, stage, current_vendor_name="", current_is_done=False):
        """업체명 및 완료상태 수정 모달 (v0.5 개선)"""
        
        st.caption(f"공정: {stage}")
        st.caption(f"현재 업체: {current_vendor_name}")
        
        # 해당 공정의 등록된 업체 목록 가져오기
        vendors_df = _self.db.get_vendors(stage)
        
        if not vendors_df.empty:
            # 등록된 업체가 있으면 드롭다운
            vendor_options = [current_vendor_name] + [v for v in vendors_df['vendor_name'].tolist() if v != current_vendor_name]
            new_vendor = st.selectbox(
                "업체 선택",
                vendor_options,
                key=f"edit_vendor_select_{order_id}_{stage}"
            )
        else:
            # 등록된 업체가 없으면 직접 입력
            new_vendor = st.text_input(
                "업체명",
                value=current_vendor_name,
                key=f"edit_vendor_input_{order_id}_{stage}"
            )
        
        is_complete = st.checkbox(
            "완료",
            value=current_is_done,
            key=f"edit_complete_{order_id}_{stage}"
        )
        
        # 버튼
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("취소", use_container_width=True, key=f"cancel_{order_id}_{stage}"):
                st.rerun()
        
        with col2:
            if st.button("💾 저장", use_container_width=True, type="primary", key=f"save_{order_id}_{stage}"):
                try:
                    from datetime import date
                    
                    # 새 이벤트 추가 (업체명 + 완료상태)
                    _self.db.add_process_event(
                        order_id=order_id,
                        stage=stage,
                        progress=100 if is_complete else 0,
                        done_date=date.today() if is_complete else None,
                        vendor=new_vendor,
                        note=f"업체 수정: {new_vendor}"
                    )
                    
                    st.success("수정 완료!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"수정 실패: {e}")

    def render_project_summary_table(_self, customer_id=None):
        """프로젝트 요약 테이블 (편집 가능)"""
        st.subheader("📊 프로젝트 요약")
        
        projects_df = _self.wip.get_projects_with_orders(customer_id)
        
        if projects_df.empty:
            st.info("📋 프로젝트가 없습니다.")
            return
        
        # 표시용 데이터프레임 준비
        display_df = projects_df.copy()
        
        # 납기일 포맷팅
        display_df['납기일'] = display_df['final_due_date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime') 
            else str(x) if pd.notna(x) and x != '' else ''
        )
        
        # 설치완료일 포맷팅
        display_df['설치완료일'] = display_df['installation_completed_date'].apply(
            lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) and hasattr(x, 'strftime')
            else str(x) if pd.notna(x) and x != '' else ''
        )
        
        # 납기 상태 아이콘
        def get_status_icon(row):
            if row['warning_level'] == 'overdue':
                return f"🔴 {row['d_day']}"
            elif row['warning_level'] == 'urgent':
                return f"🟠 {row['d_day']}"
            elif row['warning_level'] == 'warning':
                return f"🟡 {row['d_day']}"
            else:
                return f"✅ {row['d_day']}"
        
        display_df['납기상태'] = display_df.apply(get_status_icon, axis=1)
        
        # 서류 발행 상태
        display_df['세금계산서'] = display_df['tax_invoice_issued'].apply(lambda x: '✅' if x else '⚪')
        display_df['거래명세서'] = display_df['trade_statement_issued'].apply(lambda x: '✅' if x else '⚪')
        
        # 인원/일수 처리
        display_df['인원'] = display_df['installation_staff_count'].apply(
            lambda x: f"{int(x)}명" if pd.notna(x) else ''
        )
        display_df['일수'] = display_df['installation_days'].apply(
            lambda x: f"{int(x)}일" if pd.notna(x) else ''
        )
        
        # 컬럼 선택
        final_columns = [
            'project_name', 'contract_type', '납기일', '납기상태',
            '설치완료일', '인원', '일수', '세금계산서', '거래명세서',
            'order_count', 'total_progress'
        ]
        
        display_df = display_df[final_columns]
        
        # 컬럼명 한글화
        display_df = display_df.rename(columns={
            'project_name': '프로젝트',
            'contract_type': '관급/사급',
            'order_count': '발주건수',
            'total_progress': '전체진행률(%)'
        })
        
        # 편집 가능한 테이블
        st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            disabled=['프로젝트', '관급/사급', '납기일', '납기상태', '발주건수', '전체진행률(%)'],
            column_config={
                "전체진행률(%)": st.column_config.ProgressColumn(
                    "전체진행률",
                    min_value=0,
                    max_value=100,
                ),
                "설치완료일": st.column_config.DateColumn(
                    "설치완료일",
                    format="YYYY-MM-DD"
                ),
            },
            key="project_summary_table"
        )
        
        st.caption("💡 설치완료일, 인원, 일수는 직접 수정할 수 있습니다. (현재는 표시만 가능, 저장 기능은 다음 단계에서 구현)")
        
        return projects_df
# ============================================================================
# 메인 앱
# ============================================================================

def main(allowed_tenants=None):
    """WIP 앱 메인 함수 (v0.8 - 상용화 버전)

    Args:
        allowed_tenants: 사용자가 접근할 수 있는 테넌트 ID 리스트
    """
    
    # allowed_tenants가 st.session_state에 없으면 초기화
    if 'allowed_tenants' not in st.session_state:
        st.session_state.allowed_tenants = allowed_tenants

    # 접근 가능한 테넌트가 없으면 중단
    if not st.session_state.allowed_tenants:
        st.error("접근 권한이 없습니다. 관리자에게 문의하세요.")
        st.stop()

    # 사이드바 메뉴
    with st.sidebar:
        st.subheader("📱 메뉴")
        
        menu = st.radio(
            "기능 선택",
            [
                "📊 대시보드",
                "🏢 업체 관리",
                "📈 통계"
            ],
            key="wip_menu_selector"
        )
        
        st.divider()

        # 고객사 선택 (allowed_tenants 기반)
        if len(st.session_state.allowed_tenants) > 1:
            # 여러 테넌트 접근 가능 시 드롭다운 표시
            prev_tenant = st.session_state.get('tenant_id')
            
            current_index = 0
            if prev_tenant and prev_tenant in st.session_state.allowed_tenants:
                current_index = st.session_state.allowed_tenants.index(prev_tenant)

            selected_tenant = st.selectbox(
                "업체 전환", 
                st.session_state.allowed_tenants, 
                index=current_index,
                key="wip_tenant_switcher"  # 고유한 key 추가
            )
            
            if selected_tenant != prev_tenant:
                st.session_state['tenant_id'] = selected_tenant
                # Invalidate caches impacted by tenant switch
                try:
                    mgr = get_db_manager()
                    tmp_wip = WIPManager(mgr)
                    mgr.get_customers.clear()
                    mgr.get_projects.clear()
                    mgr.get_orders.clear()
                    mgr.get_process_events.clear()
                    tmp_wip.get_projects_with_orders.clear()
                    tmp_wip.get_orders_with_progress.clear()
                    tmp_wip.get_dashboard_stats.clear()
                except Exception:
                    pass
                st.rerun()
        elif st.session_state.allowed_tenants:
            # 단일 테넌트만 접근 가능 시 자동으로 선택
            selected_tenant = st.session_state.allowed_tenants[0]
        else:
            selected_tenant = None

        if selected_tenant:
            st.session_state['tenant_id'] = selected_tenant
            selected_customer = selected_tenant.upper()
            
            company_name_map = {
                'DOOHO': '두호',
                'KUKJE': '국제'
            }
            company_display = company_name_map.get(selected_customer, selected_customer)
            st.info(f"**회사명:** {company_display}")
        else:
            selected_customer = None
            st.warning("접근 가능한 업체가 없습니다.")
        
        st.divider()
        
        # 필터 섹션
        st.subheader("🔍 필터")
        
        # 1. 기간 검색
        period_type = st.radio(
            "기간 검색",
            ["전체", "년도", "월별"],
            horizontal=True,
            key="wip_period_type"
        )
        
        if period_type == "년도":
            year = st.selectbox(
                "년도 선택",
                [2024, 2025, 2026],
                index=1,
                key="wip_filter_year"
            )
        elif period_type == "월별":
            col_y, col_m = st.columns(2)
            with col_y:
                year = st.selectbox("년", [2024, 2025, 2026], index=1, key="wip_filter_year_month")
            with col_m:
                month = st.selectbox("월", list(range(1, 13)), key="wip_filter_month")
        
        # 기준 선택
        date_criteria = st.radio(
            "기준",
            ["최종납기일", "설치완료일"],
            horizontal=True,
            key="wip_date_criteria"
        )
        
        st.divider()
        
        # 2. 상태 필터
        status_filter = st.radio(
            "상태",
            ["전체", "진행중", "완료"],
            index=1,
            horizontal=True,
            key="wip_status_filter"
        )
        
        st.divider()

        # 3. 관급/사급 필터
        project_type_filter = st.radio(
            "프로젝트 유형",
            ["전체", "관급", "사급"],
            horizontal=True,
            key="wip_project_type_filter"
        )

        st.divider()

        # 완료 프로젝트 표시 토글
        show_completed = st.checkbox(
            "완료된 프로젝트 표시",
            value=False,
            help="체크 해제 시 완료된 프로젝트는 숨겨집니다"
        )
        
        st.session_state['show_completed_projects'] = show_completed

    # 회사명 매핑
    company_map = {
        'dooho': '두호',
        'kukje': '국제',
    }
    company_name = company_map.get(selected_tenant, selected_tenant)
    st.subheader(f"🗂️ {company_name} WIP 현황 관리 시스템 v0.8")

    # 데이터베이스 매니저를 캐시에서 가져옵니다.
    try:
        db_manager = get_db_manager() # ✅ 수정된 부분
        wip_manager = WIPManager(db_manager)
        ui = WIPInterface(wip_manager)
    except Exception as e:
        st.error(f"❌ 데이터베이스 초기화 실패: {e}")
        st.stop() # 여기서 멈춤

        # 캐싱 없이 직접 로딩
    # Warm key caches only once per session to avoid per-click overhead
    if 'cache_warmed' not in st.session_state:
        with st.spinner("데이터 로딩 중..."):
            _ = db_manager.get_customers()
            _ = db_manager.get_projects()
            _ = db_manager.get_vendors()
        st.session_state['cache_warmed'] = True
    
    # ========================================================================
    # 메뉴별 화면
    # ========================================================================
    
    if menu == "📊 대시보드":
        render_dashboard_page(ui, wip_manager, selected_customer)
    
    elif menu == "👥 고객사 관리":
        render_customer_page(db_manager)
    
    elif menu == "🏢 업체 관리":
        render_vendor_page(db_manager)

    elif menu == "📈 통계":
        render_statistics_page(ui, wip_manager, selected_customer)

    elif menu == "🧪 샘플 데이터 생성":
        render_sample_data_page(wip_manager)


def render_dashboard_page(ui, wip_manager, customer_id=None):
    """대시보드 페이지 - 3개 탭 구조"""
    
    # KPI 카드
    ui.render_dashboard_cards(customer_id)
    
    st.markdown("---")
    # 상태 유지형 섹션 전환(탭 회귀 방지)
    section = st.radio(
        "보기",
        ["발주 상세", "프로젝트 요약", "통계"],
        index=0,
        horizontal=True,
        key="wip_dashboard_section",
    )
    if section == "발주 상세":
        st.caption("프로젝트별 상세 정보 및 발주 관리")
        ui.render_project_summary_with_toggle(customer_id)
        return
    elif section == "프로젝트 요약":
        st.caption("프로젝트 주요 정보를 한눈에 확인")
        projects_df = wip_manager.get_projects_with_orders(customer_id)
        if not projects_df.empty:
            filtered_projects = wip_manager.apply_filters_to_projects(projects_df)
            filtered_project_ids = filtered_projects['project_id'].tolist() if not filtered_projects.empty else []
            st.session_state['filtered_project_ids'] = filtered_project_ids
        else:
            st.session_state['filtered_project_ids'] = []
        ui.render_project_summary_table_simple(customer_id)
        return
    else:
        st.caption("매출 · 프로젝트 통계")
        col1, col2 = st.columns(2)
        with col1:
            year_options = ["전체"] + [str(y) for y in range(2020, 2026)]
            selected_year = st.selectbox("연도 선택", year_options, key="dash_stats_year")
        with col2:
            month_options = ["전체"] + [f"{m:02d}월" for m in range(1, 13)]
            selected_month = st.selectbox("월 선택", month_options, key="dash_stats_month")
        year_filter = None if selected_year == "전체" else selected_year
        month_filter = None if selected_month == "전체" else int(selected_month.replace("월", ""))
        st.markdown("---")
        render_key_metrics(wip_manager.db, year_filter, month_filter)
        st.markdown("---")
        render_contract_type_ratio(wip_manager.db, year_filter)
        st.markdown("---")
        render_monthly_trend(wip_manager.db)
        st.markdown("---")
        render_top_projects(wip_manager.db, year_filter)
        return
    
    # 3개 탭 생성
    tab1, tab2, tab3 = st.tabs([
        "📊 프로젝트 요약", 
        "📋 발주 상세", 
        "📈 통계"
    ])
    
    # ==================== 탭 1: 프로젝트 요약 ====================
    with tab1:
        st.caption("프로젝트별 주요 정보를 한눈에 확인하세요")
        
        # 프로젝트 데이터 가져오기
        projects_df = wip_manager.get_projects_with_orders(customer_id)
        
        # 필터 적용
        if not projects_df.empty:
            filtered_projects = wip_manager.apply_filters_to_projects(projects_df)
            
            # 필터링된 프로젝트의 project_id 리스트
            filtered_project_ids = filtered_projects['project_id'].tolist() if not filtered_projects.empty else []
            st.session_state['filtered_project_ids'] = filtered_project_ids
        else:
            st.session_state['filtered_project_ids'] = []
        
        ui.render_project_summary_table_simple(customer_id)
    
    # ==================== 탭 2: 프로젝트 상세 ====================
    with tab2:
        st.caption("프로젝트별 상세 정보 및 발주 관리")
        ui.render_project_summary_with_toggle(customer_id)
    
    # ==================== 탭 3: 통계 ====================
    with tab3:
        st.caption("매출 및 프로젝트 통계 분석")
        
        # 기간 필터
        col1, col2 = st.columns(2)
        with col1:
            year_options = ["전체"] + [str(y) for y in range(2020, 2026)]
            selected_year = st.selectbox("연도 선택", year_options, key="dash_stats_year")
        
        with col2:
            month_options = ["전체"] + [f"{m:02d}월" for m in range(1, 13)]
            selected_month = st.selectbox("월 선택", month_options, key="dash_stats_month")
        
        year_filter = None if selected_year == "전체" else selected_year
        month_filter = None if selected_month == "전체" else int(selected_month.replace("월", ""))
        
        st.markdown("---")
        
        # 주요 지표
        render_key_metrics(wip_manager.db, year_filter, month_filter)
        
        st.markdown("---")
        
        # 관급/사급 비율
        render_contract_type_ratio(wip_manager.db, year_filter)
        
        st.markdown("---")
        
        # 월별 매출 추이
        render_monthly_trend(wip_manager.db)
        
        st.markdown("---")
        
        # 상위 프로젝트
        render_top_projects(wip_manager.db, year_filter)

def render_customer_page(db_manager):
    """고객사 관리 페이지"""
    st.subheader("👥 고객사 관리")
    
    # 고객사 목록
    customers = db_manager.get_customers()
    
    if not customers.empty:
        st.markdown("### 등록된 고객사")
        st.dataframe(
            customers[['customer_id', 'customer_name', 'contact']],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("등록된 고객사가 없습니다.")
    
    st.markdown("---")
    
    # 고객사 추가 폼
    st.markdown("### ➕ 새 고객사 등록")
    
    with st.form("add_customer_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            customer_id = st.text_input("고객사 ID", placeholder="DOOHO")
        
        with col2:
            customer_name = st.text_input("고객사명", placeholder="두호")
        
        with col3:
            contact = st.text_input("연락처", placeholder="010-1234-5678")
        
        submitted = st.form_submit_button("등록", use_container_width=True)
        
        if submitted:
            if not customer_id or not customer_name:
                st.error("고객사 ID와 이름은 필수입니다.")
            else:
                try:
                    db_manager.add_customer(customer_id, customer_name, contact)

                    # ✅ 캐시 초기화 추가
                    try:
                        db_manager.get_customers.clear()
                    except Exception:
                        pass

                    st.success(f"✅ 고객사 '{customer_name}'이(가) 등록되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 오류: {e}")
def render_statistics_page(ui, wip_manager, customer_id=None):
    """통계 페이지 렌더링 (v0.5 - 회사별 분리)"""
    st.subheader("📊 매출 및 프로젝트 통계")

    # 기간 필터
    col1, col2 = st.columns(2)
    with col1:
        year_options = ["전체"] + [str(y) for y in range(2020, 2026)]
        selected_year = st.selectbox("연도 선택", year_options, key="stats_year")

    with col2:
        month_options = ["전체"] + [f"{m:02d}월" for m in range(1, 13)]
        selected_month = st.selectbox("월 선택", month_options, key="stats_month")

    year_filter = None if selected_year == "전체" else selected_year
    month_filter = None if selected_month == "전체" else int(selected_month.replace("월", ""))

    st.markdown("---")

    # 1. 주요 지표 카드
    render_key_metrics(wip_manager.db, year_filter, month_filter, customer_id)

    st.markdown("---")

    # 2. 관급/사급 비율
    render_contract_type_ratio(wip_manager.db, year_filter, customer_id)

    st.markdown("---")

    # 3. 월별 매출 추이
    render_monthly_trend(wip_manager.db, customer_id)

    st.markdown("---")

    # 4. 상위 프로젝트
    render_top_projects(wip_manager.db, year_filter, customer_id)


def render_key_metrics(db, year=None, month=None, customer_id=None):
    """주요 지표 카드"""
    st.subheader("💰 주요 지표")

    # 🆕 customer_id 파라미터 전달
    stats = db.get_sales_statistics(year, month, customer_id)
    
    if not stats:
        st.info("해당 기간의 완료된 프로젝트가 없습니다.")
        return
    
    # 전체 합계 계산
    total_amount = sum(s['total_amount'] for s in stats)
    total_count = sum(s['project_count'] for s in stats)
    avg_amount = total_amount / total_count if total_count > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="총 매출액",
            value=f"{total_amount:,}원",
            delta=None
        )
    
    with col2:
        st.metric(
            label="완료 프로젝트 수",
            value=f"{total_count}건",
            delta=None
        )
    
    with col3:
        st.metric(
            label="평균 프로젝트 금액",
            value=f"{avg_amount:,.0f}원",
            delta=None
        )


def render_contract_type_ratio(db, year=None, customer_id=None):
    """관급/사급 비율"""
    st.subheader("📈 관급/사급 비율")
    
    # 🆕 customer_id 파라미터 전달
    ratio_data = db.get_contract_type_ratio(year, customer_id)
    
    if not ratio_data:
        st.info("데이터가 없습니다.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**프로젝트 수 기준**")
        for item in ratio_data:
            total_count = sum(r['count'] for r in ratio_data)
            percentage = (item['count'] / total_count * 100) if total_count > 0 else 0
            st.progress(percentage / 100, text=f"{item['contract_type']}: {item['count']}건 ({percentage:.1f}%)")
    
    with col2:
        st.markdown("**매출액 기준**")
        for item in ratio_data:
            total_amount = sum(r['total_amount'] for r in ratio_data)
            percentage = (item['total_amount'] / total_amount * 100) if total_amount > 0 else 0
            st.progress(percentage / 100, text=f"{item['contract_type']}: {item['total_amount']:,}원 ({percentage:.1f}%)")


def render_monthly_trend(db, customer_id=None):
    """월별 매출 추이"""
    st.subheader("📉 월별 매출 추이 (최근 12개월)")
    
    # 🆕 customer_id 파라미터 전달
    trend_data = db.get_monthly_sales_trend(12, customer_id)
    
    if not trend_data:
        st.info("데이터가 없습니다.")
        return
    
    # 데이터를 DataFrame으로 변환
    import pandas as pd
    df = pd.DataFrame(trend_data)
    
    if df.empty:
        st.info("데이터가 없습니다.")
        return
    
    # Pivot 테이블 생성
    pivot_df = df.pivot_table(
        index='month',
        columns='contract_type',
        values='total_amount',
        fill_value=0
    ).reset_index()
    
    st.bar_chart(pivot_df.set_index('month'))


def render_top_projects(db, year=None, customer_id=None):
    """상위 프로젝트"""
    st.subheader("🏆 계약금액 상위 프로젝트 (Top 10)")
    
    # 🆕 customer_id 파라미터 전달
    top_projects = db.get_top_projects_by_amount(10, year, customer_id)
    
    if not top_projects:
        st.info("데이터가 없습니다.")
        return
    
    import pandas as pd
    df = pd.DataFrame(top_projects)
    
    df['contract_amount'] = df['contract_amount'].apply(lambda x: f"{x:,}원")
    df.columns = ['프로젝트ID', '프로젝트명', '관급/사급', '계약금액', '납기일', '설치완료일']
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

def render_vendor_page(db_manager):
    """업체 관리 페이지 (v0.5 신규)"""
    st.subheader("🏢 업체 관리")
    
    # 업체 목록
    vendors = db_manager.get_vendors()
    
    if not vendors.empty:
        st.markdown("### 등록된 업체")
        
        # 표시용 데이터프레임
        display_df = vendors[['vendor_id', 'vendor_name', 'process_types', 'contact']].copy()
        display_df = display_df.rename(columns={
            'vendor_id': '업체ID',
            'vendor_name': '업체명',
            'process_types': '담당공정',
            'contact': '연락처'
        })
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("등록된 업체가 없습니다.")
    
    st.markdown("---")
    
    # 업체 추가 폼
    st.markdown("### ➕ 새 업체 등록")
    
    with st.form("add_vendor_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            vendor_id = st.text_input("업체 ID *", placeholder="VENDOR001")
            vendor_name = st.text_input("업체명 *", placeholder="오성벤딩")
            contact = st.text_input("연락처", placeholder="010-1234-5678")
        
        with col2:
            # 공정 선택 (다중 선택)
            process_options = [
                "절단/절곡", "P레이저", "레이저(판재)", 
                "벤딩", "페인트", "스티커", "입고"
            ]
            selected_processes = st.multiselect(
                "담당 공정 *",
                process_options,
                help="여러 공정 선택 가능"
            )
            
            memo = st.text_area("메모", placeholder="업체 특이사항...")
        
        submitted = st.form_submit_button("등록", use_container_width=True)
        
        if submitted:
            if not vendor_id or not vendor_name or not selected_processes:
                st.error("업체 ID, 업체명, 담당공정은 필수입니다.")
            else:
                try:
                    # 공정 목록을 쉼표로 연결
                    process_types = ",".join(selected_processes)
                    
                    db_manager.add_vendor(
                        vendor_id, 
                        vendor_name, 
                        contact, 
                        process_types, 
                        memo
                    )

                    # ✅ 캐시 초기화 추가
                    try:
                        db_manager.get_vendors.clear()
                    except Exception:
                        pass

                    st.success(f"✅ 업체 '{vendor_name}'이(가) 등록되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 오류: {e}")
    
    # 업체 삭제
    if not vendors.empty:
        st.markdown("---")
        st.markdown("### 🗑️ 업체 삭제")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            vendor_to_delete = st.selectbox(
                "삭제할 업체 선택",
                ["선택..."] + vendors['vendor_name'].tolist()
            )
        
        with col2:
            if vendor_to_delete != "선택...":
                if st.button("🗑️ 삭제", type="secondary", use_container_width=True):
                    try:
                        vendor_row = vendors[vendors['vendor_name'] == vendor_to_delete].iloc[0]
                        db_manager.delete_vendor(vendor_row['vendor_id'])

                        # ✅ 캐시 초기화 추가
                        try:
                            db_manager.get_vendors.clear()
                        except Exception:
                            pass

                        st.success(f"✅ 업체 '{vendor_to_delete}' 삭제 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 삭제 실패: {e}")

def render_sample_data_page(wip_manager):
    """샘플 데이터 생성 페이지"""
    st.subheader("🧪 샘플 데이터 생성")
    
    st.markdown("""
    테스트용 샘플 데이터를 생성합니다:
    
    **생성 내용:**
    - 고객사 2개 (두호, 국제)
    - 발주 3건 (초당초등학교 프로젝트)
    - 진행 이벤트 7건
    
    ⚠️ **주의**: 이미 같은 ID가 있으면 건너뜁니다.
    """)
    
    if st.button("🎲 샘플 데이터 생성", type="primary", use_container_width=True):
        try:
            with st.spinner("샘플 데이터 생성 중..."):
                wip_manager.create_sample_data()
            st.success("✅ 샘플 데이터가 생성되었습니다!")
            st.balloons()
            st.info("📊 '대시보드' 메뉴로 이동해서 확인해보세요!")
        except Exception as e:
            st.error(f"❌ 오류: {e}")
    
    st.markdown("---")
    
    # 데이터베이스 상태 표시
    st.markdown("### 📊 현재 데이터베이스 상태")
    
    try:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            customers = wip_manager.db.get_customers()
            st.metric("고객사", f"{len(customers)}개")
        
        with col2:
            orders = wip_manager.db.get_orders()
            st.metric("발주", f"{len(orders)}건")
        
        with col3:
            events = wip_manager.db.get_process_events()
            st.metric("이벤트", f"{len(events)}건")
    
    except Exception as e:
        st.error(f"상태 조회 실패: {e}")


# ============================================================================
# 앱 실행
# ============================================================================

if __name__ == "__main__":
    main()
