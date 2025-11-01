"""
G2B 조달청 가격정보 수집기
- 나라장터 Open API 연동
- 가격정보 자동 수집 및 DB 저장
- BOM 테이블 자재 단가 자동 업데이트
"""

import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
import time
from difflib import SequenceMatcher


class G2BPriceCollector:
    """G2B 가격정보 수집 및 관리 클래스"""

    def __init__(self, service_key: str, supabase_client=None):
        """
        Args:
            service_key: G2B OpenAPI 인증키
            supabase_client: Supabase 클라이언트 (선택)
        """
        self.service_key = service_key
        self.base_url = "http://apis.data.go.kr/1230000/ao/PriceInfoService"
        self.supabase = supabase_client

    def search_price_by_product_name(
        self,
        product_name: str,
        num_of_rows: int = 10,
        page_no: int = 1
    ) -> List[Dict]:
        """
        품명으로 가격정보 검색

        Args:
            product_name: 검색할 품명
            num_of_rows: 한 페이지당 결과 수 (기본 10개)
            page_no: 페이지 번호

        Returns:
            가격정보 리스트
        """
        endpoint = f"{self.base_url}/getPriceInfoListFcltyCmmnMtrilEngr"

        params = {
            'ServiceKey': self.service_key,
            'pageNo': page_no,
            'numOfRows': num_of_rows,
            'prdctClsfcNoNm': product_name,  # 품명으로 검색
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()

            # XML 파싱
            root = ET.fromstring(response.content)

            # 응답 코드 확인
            result_code = root.find('.//resultCode')
            if result_code is not None and result_code.text != '00':
                result_msg = root.find('.//resultMsg')
                print(f"⚠️ API 오류: {result_msg.text if result_msg is not None else 'Unknown error'}")
                return []

            # 데이터 파싱
            items = []
            for item in root.findall('.//item'):
                price_info = self._parse_price_item(item)
                if price_info:
                    items.append(price_info)

            return items

        except requests.RequestException as e:
            print(f"❌ API 요청 실패: {e}")
            return []
        except ET.ParseError as e:
            print(f"❌ XML 파싱 실패: {e}")
            return []

    def search_price_by_classification_code(
        self,
        classification_code: str,
        num_of_rows: int = 10,
        page_no: int = 1
    ) -> List[Dict]:
        """
        물품분류번호로 가격정보 검색

        Args:
            classification_code: 물품분류번호 (예: 30103698)
            num_of_rows: 한 페이지당 결과 수
            page_no: 페이지 번호

        Returns:
            가격정보 리스트
        """
        endpoint = f"{self.base_url}/getPriceInfoListFcltyCmmnMtrilEngr"

        params = {
            'ServiceKey': self.service_key,
            'pageNo': page_no,
            'numOfRows': num_of_rows,
            'prdctClsfcNo': classification_code,
        }

        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            result_code = root.find('.//resultCode')
            if result_code is not None and result_code.text != '00':
                result_msg = root.find('.//resultMsg')
                print(f"⚠️ API 오류: {result_msg.text if result_msg is not None else 'Unknown error'}")
                return []

            items = []
            for item in root.findall('.//item'):
                price_info = self._parse_price_item(item)
                if price_info:
                    items.append(price_info)

            return items

        except Exception as e:
            print(f"❌ API 요청 실패: {e}")
            return []

    def _parse_price_item(self, item: ET.Element) -> Optional[Dict]:
        """XML item 요소를 딕셔너리로 파싱"""
        try:
            # 게시일시 파싱
            ntice_dt_str = self._get_text(item, 'nticeDt')
            ntice_dt = None
            if ntice_dt_str:
                try:
                    ntice_dt = datetime.strptime(ntice_dt_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    try:
                        ntice_dt = datetime.strptime(ntice_dt_str, '%Y-%m-%d')
                    except ValueError:
                        pass

            # 가격 파싱
            price_str = self._get_text(item, 'prce')
            price = float(price_str) if price_str else None

            return {
                'prce_ntice_no': self._get_text(item, 'prceNticeNo'),
                'ntice_dt': ntice_dt,
                'bsns_div_cd': self._get_text(item, 'bsnsDivCd'),
                'bsns_div_nm': self._get_text(item, 'bsnsDivNm'),
                'prdct_clsfc_no': self._get_text(item, 'prdctClsfcNo'),
                'prdct_clsfc_no_nm': self._get_text(item, 'prdctClsfcNoNm'),
                'prdct_idnt_no': self._get_text(item, 'prdctIdntNo'),
                'invst_dept_nm': self._get_text(item, 'invstDeptNm'),
                'invst_dept_tel_no': self._get_text(item, 'invstDeptTelNo'),
                'invst_ofcl_nm': self._get_text(item, 'invstOfclNm'),
                'krn_prdct_nm': self._get_text(item, 'krnPrdctNm'),
                'unit': self._get_text(item, 'unit'),
                'prce': price,
                'sply_jrsdct_rgn_nm': self._get_text(item, 'splyJrsdctRgnNm'),
                'etc_cntnts': self._get_text(item, 'etcCntnts'),
                'mtrl_cst': self._get_text(item, 'mtrlcst'),
                'lbr_cst': self._get_text(item, 'lbrcst'),
                'gnrl_expns': self._get_text(item, 'gnrlexpns'),
                'prce_div': self._get_text(item, 'prceDiv'),
                'dlvry_cndtn_nm': self._get_text(item, 'dlvryCndtnNm'),
                'distb_step': self._get_text(item, 'distbStep'),
                'pay_cndtn': self._get_text(item, 'payCndtn'),
                'vat_yn_nm': self._get_text(item, 'vatYnNm'),
                'prodct_fld': self._get_text(item, 'prodctFld'),
            }
        except Exception as e:
            print(f"⚠️ 아이템 파싱 오류: {e}")
            return None

    def _get_text(self, element: ET.Element, tag: str) -> Optional[str]:
        """XML 요소에서 텍스트 추출"""
        child = element.find(tag)
        return child.text if child is not None and child.text else None

    def save_to_supabase(
        self,
        price_items: List[Dict],
        tenant_id: str = 'dooho'
    ) -> int:
        """
        가격정보를 Supabase에 저장

        Args:
            price_items: 저장할 가격정보 리스트
            tenant_id: 테넌트 ID

        Returns:
            저장된 레코드 수
        """
        if not self.supabase:
            print("⚠️ Supabase 클라이언트가 설정되지 않았습니다.")
            return 0

        saved_count = 0

        for item in price_items:
            try:
                # 데이터 준비
                data = {
                    'tenant_id': tenant_id,
                    'prce_ntice_no': item.get('prce_ntice_no'),
                    'ntice_dt': item.get('ntice_dt').isoformat() if item.get('ntice_dt') else None,
                    'bsns_div_cd': item.get('bsns_div_cd'),
                    'bsns_div_nm': item.get('bsns_div_nm'),
                    'prdct_clsfc_no': item.get('prdct_clsfc_no'),
                    'prdct_clsfc_no_nm': item.get('prdct_clsfc_no_nm'),
                    'prdct_idnt_no': item.get('prdct_idnt_no'),
                    'invst_dept_nm': item.get('invst_dept_nm'),
                    'invst_dept_tel_no': item.get('invst_dept_tel_no'),
                    'invst_ofcl_nm': item.get('invst_ofcl_nm'),
                    'krn_prdct_nm': item.get('krn_prdct_nm'),
                    'unit': item.get('unit'),
                    'prce': item.get('prce'),
                    'sply_jrsdct_rgn_nm': item.get('sply_jrsdct_rgn_nm'),
                    'etc_cntnts': item.get('etc_cntnts'),
                    'mtrl_cst': item.get('mtrl_cst'),
                    'lbr_cst': item.get('lbr_cst'),
                    'gnrl_expns': item.get('gnrl_expns'),
                    'prce_div': item.get('prce_div'),
                    'dlvry_cndtn_nm': item.get('dlvry_cndtn_nm'),
                    'distb_step': item.get('distb_step'),
                    'pay_cndtn': item.get('pay_cndtn'),
                    'vat_yn_nm': item.get('vat_yn_nm'),
                    'prodct_fld': item.get('prodct_fld'),
                    'is_active': True,
                    'last_updated_from_api': datetime.now().isoformat(),
                }

                # 중복 체크 (가격계시번호 기준)
                if item.get('prce_ntice_no'):
                    existing = self.supabase.table('g2b_price_info').select('id, prce').eq(
                        'prce_ntice_no', item['prce_ntice_no']
                    ).eq('tenant_id', tenant_id).execute()

                    if existing.data:
                        # 기존 레코드 업데이트
                        record_id = existing.data[0]['id']
                        old_price = existing.data[0].get('prce')

                        self.supabase.table('g2b_price_info').update(data).eq('id', record_id).execute()

                        # 가격 변동 이력 저장
                        if old_price and item.get('prce') and old_price != item['prce']:
                            change_pct = ((item['prce'] - old_price) / old_price) * 100
                            self.supabase.table('g2b_price_history').insert({
                                'tenant_id': tenant_id,
                                'g2b_price_info_id': record_id,
                                'old_price': old_price,
                                'new_price': item['prce'],
                                'change_percentage': round(change_pct, 2),
                            }).execute()
                    else:
                        # 새 레코드 삽입
                        self.supabase.table('g2b_price_info').insert(data).execute()
                else:
                    # 가격계시번호가 없으면 그냥 삽입
                    self.supabase.table('g2b_price_info').insert(data).execute()

                saved_count += 1

            except Exception as e:
                print(f"⚠️ 저장 실패: {e}")
                continue

        return saved_count

    def match_with_bom(
        self,
        tenant_id: str = 'dooho',
        similarity_threshold: float = 0.7
    ) -> int:
        """
        BOM 테이블의 자재와 G2B 가격정보를 매칭하여 단가 업데이트

        Args:
            tenant_id: 테넌트 ID
            similarity_threshold: 유사도 임계값 (0.0 ~ 1.0)

        Returns:
            업데이트된 BOM 레코드 수
        """
        if not self.supabase:
            print("⚠️ Supabase 클라이언트가 설정되지 않았습니다.")
            return 0

        # BOM 테이블에서 단가가 없는 자재 조회
        bom_items = self.supabase.table('bom').select('*').eq(
            'tenant_id', tenant_id
        ).is_('unit_price', 'null').execute()

        if not bom_items.data:
            print("ℹ️ 단가 업데이트가 필요한 BOM 항목이 없습니다.")
            return 0

        updated_count = 0

        for bom_item in bom_items.data:
            material_name = bom_item.get('material_name', '')
            standard = bom_item.get('standard', '')

            if not material_name:
                continue

            # G2B에서 유사한 품명 검색
            g2b_prices = self.supabase.table('g2b_price_info').select('*').eq(
                'tenant_id', tenant_id
            ).eq('is_active', True).execute()

            # 유사도 계산하여 가장 일치하는 항목 찾기
            best_match = None
            best_score = 0.0

            for g2b_item in g2b_prices.data:
                g2b_name = g2b_item.get('prdct_clsfc_no_nm', '')
                g2b_spec = g2b_item.get('krn_prdct_nm', '')

                # 품명 유사도
                name_similarity = SequenceMatcher(None, material_name, g2b_name).ratio()

                # 규격 유사도 (규격이 있는 경우)
                spec_similarity = 0.0
                if standard and g2b_spec:
                    spec_similarity = SequenceMatcher(None, standard, g2b_spec).ratio()

                # 전체 점수 (품명 70%, 규격 30%)
                total_score = (name_similarity * 0.7) + (spec_similarity * 0.3)

                if total_score > best_score:
                    best_score = total_score
                    best_match = g2b_item

            # 임계값 이상이면 업데이트
            if best_match and best_score >= similarity_threshold:
                try:
                    self.supabase.table('bom').update({
                        'unit_price': best_match.get('prce'),
                    }).eq('id', bom_item['id']).execute()

                    # G2B 가격정보에 매칭 정보 저장
                    self.supabase.table('g2b_price_info').update({
                        'matched_material_name': material_name,
                        'matched_standard': standard,
                        'match_score': round(best_score * 100, 2),
                    }).eq('id', best_match['id']).execute()

                    updated_count += 1
                    print(f"✅ 매칭 완료: {material_name} → {best_match.get('prdct_clsfc_no_nm')} (유사도: {best_score:.2%})")

                except Exception as e:
                    print(f"⚠️ BOM 업데이트 실패: {e}")
                    continue

        return updated_count

    def bulk_collect_by_bom(
        self,
        tenant_id: str = 'dooho',
        delay_seconds: float = 0.5
    ) -> Dict[str, int]:
        """
        BOM 테이블의 모든 자재에 대해 G2B 가격정보 수집

        Args:
            tenant_id: 테넌트 ID
            delay_seconds: API 호출 간 대기 시간 (초)

        Returns:
            통계 정보 (수집된 항목 수, 저장된 레코드 수 등)
        """
        if not self.supabase:
            print("⚠️ Supabase 클라이언트가 설정되지 않았습니다.")
            return {'error': 'No Supabase client'}

        # BOM 테이블에서 고유 자재명 조회
        bom_items = self.supabase.table('bom').select('material_name').eq(
            'tenant_id', tenant_id
        ).execute()

        unique_materials = list(set([item['material_name'] for item in bom_items.data]))

        total_collected = 0
        total_saved = 0

        print(f"📊 총 {len(unique_materials)}개 자재에 대해 가격정보 수집 시작...")

        for i, material_name in enumerate(unique_materials, 1):
            print(f"[{i}/{len(unique_materials)}] {material_name} 검색 중...")

            # API 호출
            price_items = self.search_price_by_product_name(material_name, num_of_rows=5)

            if price_items:
                total_collected += len(price_items)

                # DB 저장
                saved = self.save_to_supabase(price_items, tenant_id)
                total_saved += saved

                print(f"  ✅ {len(price_items)}개 발견, {saved}개 저장")
            else:
                print(f"  ⚠️ 가격정보 없음")

            # API 호출 제한 방지
            time.sleep(delay_seconds)

        return {
            'total_materials': len(unique_materials),
            'total_collected': total_collected,
            'total_saved': total_saved,
        }


# 사용 예시 함수
def example_usage():
    """사용 예시"""
    from app.config_supabase import get_supabase_client

    # G2B API 키 (환경변수에서 읽기)
    g2b_api_key = os.getenv('G2B_API_KEY', 'YOUR_API_KEY_HERE')

    # Supabase 클라이언트
    supabase = get_supabase_client()

    # 수집기 초기화
    collector = G2BPriceCollector(service_key=g2b_api_key, supabase_client=supabase)

    # 1. 품명으로 검색
    print("\n=== 1. 품명으로 가격정보 검색 ===")
    results = collector.search_price_by_product_name("소화용기구", num_of_rows=5)
    print(f"검색 결과: {len(results)}건")
    for item in results:
        print(f"  - {item['prdct_clsfc_no_nm']}: {item['prce']:,}원 ({item['unit']})")

    # 2. DB 저장
    if results:
        saved = collector.save_to_supabase(results, tenant_id='dooho')
        print(f"\n저장 완료: {saved}건")

    # 3. BOM과 매칭하여 단가 업데이트
    print("\n=== 2. BOM 단가 자동 업데이트 ===")
    updated = collector.match_with_bom(tenant_id='dooho', similarity_threshold=0.7)
    print(f"업데이트 완료: {updated}건")

    # 4. BOM 기반 전체 수집
    print("\n=== 3. BOM 기반 전체 가격정보 수집 ===")
    stats = collector.bulk_collect_by_bom(tenant_id='dooho', delay_seconds=0.5)
    print(f"통계: {stats}")


if __name__ == "__main__":
    example_usage()
