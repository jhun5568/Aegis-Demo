"""
PtopEngine - Produce-to-Pay 비즈니스 로직 엔진
견적 → 발주 → 내역서 생성 전 과정 관리

Multi-tenant 지원:
- 각 엔진 인스턴스는 특정 tenant_id에 귀속
- 모든 데이터베이스 쿼리는 tenant_id 필터링 적용
"""

from typing import Optional, List, Dict, Any
import pandas as pd
from supabase import Client
import re


class PtopEngine:
    """
    Produce-to-Pay 비즈니스 로직 엔진

    Usage:
        from supabase import create_client
        from utils.ptop_engine import PtopEngine

        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        engine = PtopEngine(supabase, tenant_id='dooho')

        # 모델 검색
        models = engine.search_models('DAL')

        # BOM 계산
        bom = engine.calculate_bom_for_span('DH001', span_count=10)
    """

    # 상수
    PIPE_STANDARD_LENGTH_M = 6.0  # PIPE 발주 단위 (6m)
    VAT_RATE = 0.1  # 부가세율 10%

    def __init__(self, supabase_client: Client, tenant_id: str):
        """
        PtopEngine 초기화

        Args:
            supabase_client: Supabase 클라이언트 인스턴스
            tenant_id: 고객사 ID ('dooho', 'kukje' 등)
        """
        self.db = supabase_client
        self.tenant = tenant_id

    # ========================================================================
    # 모델 관리
    # ========================================================================

    def get_model_by_id(self, model_id: str) -> Optional[Dict]:
        """
        모델 ID로 모델 정보 조회

        Args:
            model_id: 모델 ID (예: 'DH001')

        Returns:
            모델 정보 딕셔너리 또는 None
        """
        try:
            result = self.db.schema('ptop').table('models')\
                .select('*')\
                .eq('tenant_id', self.tenant)\
                .eq('model_id', model_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ get_model_by_id 오류: {e}")
            return None

    def get_model_by_name(self, model_name: str) -> Optional[Dict]:
        """
        모델명으로 모델 정보 조회

        Args:
            model_name: 모델명 (예: 'DAL01-2012')

        Returns:
            모델 정보 딕셔너리 또는 None
        """
        try:
            result = self.db.schema('ptop').table('models')\
                .select('*')\
                .eq('tenant_id', self.tenant)\
                .eq('model_name', model_name)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ get_model_by_name 오류: {e}")
            return None

    def search_models(self, keyword: str = '') -> pd.DataFrame:
        """
        모델 검색 (키워드 기반)

        Args:
            keyword: 검색 키워드 (빈 문자열이면 전체 조회)

        Returns:
            모델 목록 DataFrame
        """
        try:
            query = self.db.schema('ptop').table('models')\
                .select('*')\
                .eq('tenant_id', self.tenant)

            if keyword:
                query = query.ilike('model_name', f'%{keyword}%')

            result = query.order('model_name').execute()
            return pd.DataFrame(result.data)
        except Exception as e:
            print(f"❌ search_models 오류: {e}")
            return pd.DataFrame()

    def get_all_models(self) -> pd.DataFrame:
        """
        전체 모델 목록 조회

        Returns:
            모델 목록 DataFrame
        """
        return self.search_models(keyword='')

    # ========================================================================
    # BOM 관리
    # ========================================================================

    def get_bom(self, model_id: str) -> pd.DataFrame:
        """
        모델의 기본 BOM 조회 (경간당 수량)

        Args:
            model_id: 모델 ID

        Returns:
            BOM DataFrame
        """
        try:
            result = self.db.schema('ptop').table('bom')\
                .select('*')\
                .eq('tenant_id', self.tenant)\
                .eq('model_id', model_id)\
                .execute()
            return pd.DataFrame(result.data)
        except Exception as e:
            print(f"❌ get_bom 오류: {e}")
            return pd.DataFrame()

    def calculate_bom_for_span(self, model_id: str, span_count: int) -> pd.DataFrame:
        """
        경간 수에 따른 BOM 계산 (핵심 로직!)

        Args:
            model_id: 모델 ID
            span_count: 경간 수

        Returns:
            계산된 BOM DataFrame (total_quantity, order_quantity, amount 포함)
        """
        bom_base = self.get_bom(model_id)

        if bom_base.empty:
            return bom_base

        # 1. 경간당 수량 * 경간 수 = 총 필요 수량
        bom_base['total_quantity'] = bom_base['quantity'] * span_count

        # 2. PIPE 환산 (6m 단위로 올림)
        bom_base['order_quantity'] = bom_base.apply(
            lambda row: self._convert_pipe_quantity(row['total_quantity'], row.get('category', ''))
            if 'PIPE' in str(row.get('category', '')).upper()
            else row['total_quantity'],
            axis=1
        )

        # 3. 금액 계산
        bom_base['unit_price'] = bom_base['unit_price'].fillna(0)
        bom_base['amount'] = bom_base['order_quantity'] * bom_base['unit_price']

        return bom_base

    def _convert_pipe_quantity(self, total_m: float, category: str) -> float:
        """
        PIPE 수량을 6m 단위(EA)로 환산

        Args:
            total_m: 총 미터 수
            category: 자재 카테고리

        Returns:
            올림 처리된 EA 수량
        """
        if pd.isna(total_m) or total_m <= 0:
            return 0

        # 올림 처리: -(-x // y) = ceil(x / y)
        return -(-total_m // self.PIPE_STANDARD_LENGTH_M)

    def add_bom_item(self, model_id: str, material_data: Dict) -> bool:
        """
        BOM에 자재 추가

        Args:
            model_id: 모델 ID
            material_data: 자재 정보 딕셔너리
                {
                    'material_name': '각파이프',
                    'standard': '75*75*2.0T',
                    'quantity': 1.4,
                    'unit': 'M',
                    'category': 'HGI PIPE',
                    'notes': '...'
                }

        Returns:
            성공 여부
        """
        try:
            # 모델 존재 확인
            model = self.get_model_by_id(model_id)
            if not model:
                print(f"❌ 모델 {model_id}를 찾을 수 없습니다.")
                return False

            # BOM 데이터 준비
            bom_data = {
                'tenant_id': self.tenant,
                'model_id': model_id,
                'model_name': model.get('model_name'),
                'material_name': material_data.get('material_name'),
                'standard': material_data.get('standard'),
                'quantity': material_data.get('quantity', 0),
                'unit': material_data.get('unit', 'EA'),
                'category': material_data.get('category'),
                'material_type': material_data.get('material_type'),
                'notes': material_data.get('notes', ''),
                'unit_price': material_data.get('unit_price')
            }

            # Supabase에 삽입
            self.db.schema('ptop').table('bom').insert(bom_data).execute()
            print(f"✅ BOM 항목 추가 완료: {material_data.get('material_name')}")
            return True

        except Exception as e:
            print(f"❌ add_bom_item 오류: {e}")
            return False

    def delete_bom_item(self, model_id: str, material_name: str, standard: str) -> bool:
        """
        BOM 항목 삭제

        Args:
            model_id: 모델 ID
            material_name: 자재명
            standard: 규격

        Returns:
            성공 여부
        """
        try:
            # Supabase에서 삭제
            result = self.db.schema('ptop').table('bom').delete().match({
                'tenant_id': self.tenant,
                'model_id': model_id,
                'material_name': material_name,
                'standard': standard
            }).execute()

            print(f"✅ BOM 항목 삭제 완료: {material_name} ({standard})")
            return True

        except Exception as e:
            print(f"❌ delete_bom_item 오류: {e}")
            return False

    # ========================================================================
    # 자재 단가 조회
    # ========================================================================

    def find_material_price(self, material_name: str, standard: str) -> Optional[float]:
        """
        주자재/부자재 단가 조회

        Args:
            material_name: 자재명
            standard: 규격

        Returns:
            단가 또는 None
        """
        # 1. main_materials 검색
        price = self._find_main_material_price(material_name, standard)
        if price is not None:
            return price

        # 2. sub_materials 검색
        price = self._find_sub_material_price(material_name, standard)
        if price is not None:
            return price

        # 3. inventory 검색
        price = self._find_inventory_price(material_name, standard)
        return price

    def _find_main_material_price(self, material_name: str, standard: str) -> Optional[float]:
        """주자재 단가 조회"""
        try:
            result = self.db.schema('ptop').table('main_materials')\
                .select('unit_price')\
                .eq('tenant_id', self.tenant)\
                .eq('product_name', material_name)\
                .eq('standard', standard)\
                .execute()

            return result.data[0]['unit_price'] if result.data else None
        except:
            return None

    def _find_sub_material_price(self, material_name: str, standard: str) -> Optional[float]:
        """부자재 단가 조회"""
        try:
            result = self.db.schema('ptop').table('sub_materials')\
                .select('unit_price')\
                .eq('tenant_id', self.tenant)\
                .eq('product_name', material_name)\
                .eq('standard', standard)\
                .execute()

            return result.data[0]['unit_price'] if result.data else None
        except:
            return None

    def _find_inventory_price(self, material_name: str, standard: str) -> Optional[float]:
        """재고 단가 조회"""
        try:
            result = self.db.schema('ptop').table('inventory')\
                .select('unit_price')\
                .eq('tenant_id', self.tenant)\
                .eq('product_name', material_name)\
                .eq('standard', standard)\
                .execute()

            return result.data[0]['unit_price'] if result.data else None
        except:
            return None

    # ========================================================================
    # 가격 조회
    # ========================================================================

    def get_model_price(self, model_name: str) -> Optional[float]:
        """
        모델 판매 단가 조회

        Args:
            model_name: 모델명

        Returns:
            단가 또는 None
        """
        try:
            result = self.db.schema('ptop').table('pricing')\
                .select('unit_price')\
                .eq('tenant_id', self.tenant)\
                .eq('model_name', model_name)\
                .execute()

            return result.data[0]['unit_price'] if result.data else None
        except Exception as e:
            print(f"❌ get_model_price 오류: {e}")
            return None

    def search_pricing(self, keyword: str = '') -> pd.DataFrame:
        """
        가격표 검색

        Args:
            keyword: 검색 키워드

        Returns:
            가격표 DataFrame
        """
        try:
            query = self.db.schema('ptop').table('pricing')\
                .select('*')\
                .eq('tenant_id', self.tenant)

            if keyword:
                query = query.ilike('model_name', f'%{keyword}%')

            result = query.order('model_name').execute()
            return pd.DataFrame(result.data)
        except Exception as e:
            print(f"❌ search_pricing 오류: {e}")
            return pd.DataFrame()

    # ========================================================================
    # 견적서 생성
    # ========================================================================

    def generate_quotation_summary(self, bom_df: pd.DataFrame) -> Dict[str, Any]:
        """
        BOM 기반 견적 요약 생성

        Args:
            bom_df: calculate_bom_for_span()로 계산된 BOM DataFrame

        Returns:
            견적 요약 딕셔너리
            {
                'supply_price': 공급가액,
                'vat': 부가세,
                'total_amount': 총액,
                'item_count': 항목 수,
                'bom_items': BOM 항목 리스트
            }
        """
        if bom_df.empty:
            return {
                'supply_price': 0,
                'vat': 0,
                'total_amount': 0,
                'item_count': 0,
                'bom_items': []
            }

        supply_price = bom_df['amount'].sum()
        vat = supply_price * self.VAT_RATE
        total = supply_price + vat

        return {
            'supply_price': round(supply_price, 2),
            'vat': round(vat, 2),
            'total_amount': round(total, 2),
            'item_count': len(bom_df),
            'bom_items': bom_df.to_dict('records')
        }

    # ========================================================================
    # 자재 검색
    # ========================================================================

    def search_main_materials(self, keyword: str = '') -> pd.DataFrame:
        """주자재 검색"""
        try:
            query = self.db.schema('ptop').table('main_materials')\
                .select('*')\
                .eq('tenant_id', self.tenant)

            if keyword:
                query = query.ilike('product_name', f'%{keyword}%')

            result = query.order('product_name').execute()
            return pd.DataFrame(result.data)
        except Exception as e:
            print(f"❌ search_main_materials 오류: {e}")
            return pd.DataFrame()

    def search_sub_materials(self, keyword: str = '') -> pd.DataFrame:
        """부자재 검색"""
        try:
            query = self.db.schema('ptop').table('sub_materials')\
                .select('*')\
                .eq('tenant_id', self.tenant)

            if keyword:
                query = query.ilike('product_name', f'%{keyword}%')

            result = query.order('product_name').execute()
            return pd.DataFrame(result.data)
        except Exception as e:
            print(f"❌ search_sub_materials 오류: {e}")
            return pd.DataFrame()

    def search_inventory(self, keyword: str = '') -> pd.DataFrame:
        """재고 검색"""
        try:
            query = self.db.schema('ptop').table('inventory')\
                .select('*')\
                .eq('tenant_id', self.tenant)

            if keyword:
                query = query.or_(f'product_name.ilike.%{keyword}%,standard.ilike.%{keyword}%,item_id.ilike.%{keyword}%')

            result = query.order('product_name').execute()
            return pd.DataFrame(result.data)
        except Exception as e:
            print(f"❌ search_inventory 오류: {e}")
            return pd.DataFrame()

    # ========================================================================
    # 향후 확장 기능 (Placeholder)
    # ========================================================================

    def create_purchase_order(self, quotation_data: Dict) -> Optional[str]:
        """
        발주서 생성

        Args:
            quotation_data: 견적 데이터

        Returns:
            발주서 ID 또는 None
        """
        # TODO: 구현
        print("⚠️ create_purchase_order: 향후 구현 예정")
        return None

    def generate_delivery_note(self, order_id: str) -> Optional[bytes]:
        """
        납품 내역서 생성

        Args:
            order_id: 발주서 ID

        Returns:
            PDF 바이트 데이터 또는 None
        """
        # TODO: 구현
        print("⚠️ generate_delivery_note: 향후 구현 예정")
        return None


# ========================================================================
# 편의 함수 (캐싱 지원)
# ========================================================================

def get_cached_ptop_engine(tenant_id: str) -> PtopEngine:
    """
    캐시된 PtopEngine 인스턴스 반환
    
    Args:
        tenant_id: 테넌트 ID ('dooho', 'kukje' 등)
    
    Returns:
        PtopEngine 인스턴스
    """
    from config_supabase import get_supabase_client
    supabase = get_supabase_client()
    return PtopEngine(supabase, tenant_id)
