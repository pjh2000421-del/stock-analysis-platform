"""
OpenDART 기반 재무제표 Provider Adapter (요구사항 5).

fnlttSinglAcntAll API를 사용하여 연결/별도 재무제표 주요 계정을 조회한다.
DART API 특성상 계정명이 기업별로 다소 다를 수 있어, 표준 계정명 후보군으로 매칭한다.
"""
from __future__ import annotations

from datetime import date, datetime

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import FinancialStatementProvider, ProviderResult, RawFinancialStatement
from app.providers.dart_common import get_corp_code

logger = get_logger(__name__)

DART_FINANCIAL_ENDPOINT = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
DART_SHARES_ENDPOINT = "https://opendart.fss.or.kr/api/stockTotqySttus.json"

# 계정명 후보 매핑 (표준계정명이 기업/업종에 따라 다르게 공시되는 경우 대비)
ACCOUNT_NAME_CANDIDATES: dict[str, list[str]] = {
    "revenue": ["매출액", "수익(매출액)", "영업수익"],
    "operating_income": ["영업이익", "영업이익(손실)"],
    "net_income": ["당기순이익", "당기순이익(손실)"],
    "assets": ["자산총계"],
    "liabilities": ["부채총계"],
    "equity": ["자본총계"],
    "current_assets": ["유동자산"],
    "current_liabilities": ["유동부채"],
    "inventory": ["재고자산"],
    "cash_and_equivalents": ["현금및현금성자산"],
    # 감가상각비는 보통 현금흐름표에 하나의 합산 계정으로 공시되지만,
    # 유형/무형자산 상각을 분리 공시하는 기업도 있어 둘 다 후보로 둔다.
    "depreciation_amortization": ["감가상각비", "감가상각비및무형자산상각비"],
}

# EBITDA/EV 계산용 D&A를 유형자산감가상각비 + 무형자산상각비(+ 리스 사용권자산 상각)로
# 별도 공시하는 경우의 후보.
_DEPRECIATION_BREAKDOWN_CANDIDATES = [
    "유형자산감가상각비",
    "무형자산상각비",
    "사용권자산감가상각비",
]

# 삼성전자처럼 현금흐름표에서 감가상각비를 다른 비현금 조정 항목(손상차손, 이연법인세,
# 지분법손익 등)과 함께 "조정"(현금흐름표 상 당기순이익 조정 합계) 한 줄로만 합산 공시하는
# 대기업은 DART "단일회사 전체 재무제표"(fnlttSinglAcntAll, 주요계정 API) 응답 자체에
# 감가상각비가 별도 계정으로 나오지 않는다 - 계정명 후보 문제가 아니라 이 API가 제공하는
# 데이터의 한계다. 이 경우 위 후보들로 감가상각비를 못 찾으면, 차선책으로 이 "조정" 합계를
# EBITDA 근사치의 재료로 사용한다(단, 감가상각비 외에 다른 비현금 항목도 섞여있으므로
# 반드시 "추정치"로 표시한다 - 요구사항 74).
_NON_CASH_ADJUSTMENTS_CANDIDATES = ["조정"]

# 총차입금(이자부부채) 계산에 합산할 항목들. 각 항목은 서로 다른 계정이므로
# "첫 매칭값 사용"이 아니라 "존재하는 것을 모두 합산"한다.
_BORROWINGS_CANDIDATES = ["단기차입금", "유동성장기부채", "사채", "장기차입금", "유동성사채"]

# _match_flexible()의 net_income contains_any 후보. "당기순이익"/"당기순손실" 외에도
# 연결재무제표에서 "당기연결순이익"처럼 접두어가 붙는 경우(예: RFHIC 218410)를 위해
# "당기연결순이익"/"당기연결순손실"도 포함한다 - 지배기업 귀속분 행이 아예 없는
# 기업(비지배지분이 없어 연결순이익=지배기업 귀속분인 경우)에서는 이게 유일한 매칭
# 대상이 될 수 있다.
_NET_INCOME_CONTAINS_ANY = ["당기순이익", "당기순손실", "당기연결순이익", "당기연결순손실"]


def _match_amount(rows: list[dict], candidates: list[str], sj_div: str | None = None) -> float | None:
    """계정명이 candidates에 포함되는 첫 행의 금액을 반환한다.

    sj_div(BS/IS/CF 등 재무제표 구분)를 지정하면 해당 표에서만 찾는다. "조정"처럼
    계정명이 흔해서 다른 표의 동명 항목과 혼동될 수 있는 경우 반드시 지정해야 한다.
    """
    for row in rows:
        if sj_div is not None and (row.get("sj_div") or "") != sj_div:
            continue
        name = (row.get("account_nm") or "").strip()
        if name in candidates:
            raw = row.get("thstrm_amount", "")
            try:
                return float(str(raw).replace(",", ""))
            except (ValueError, TypeError):
                continue
    return None


def _sum_amounts(rows: list[dict], candidates: list[str]) -> float | None:
    """서로 다른 계정과목(예: 단기차입금 + 사채 + 장기차입금)을 모두 합산한다.

    하나도 매칭되지 않으면 None을 반환한다(0으로 단정하면 "차입금이 전혀 없다"는
    확정적 주장이 되는데, 실제로는 우리 계정명 후보가 그 기업의 공시 방식과
    맞지 않아 못 찾은 것일 수도 있기 때문 - 요구사항 74: 숫자를 함부로 만들지 않는다).
    """
    total = 0.0
    found = False
    for row in rows:
        name = (row.get("account_nm") or "").strip()
        if name in candidates:
            raw = row.get("thstrm_amount", "")
            try:
                total += float(str(raw).replace(",", ""))
                found = True
            except (ValueError, TypeError):
                continue
    return total if found else None


def _match_flexible(
    rows: list[dict],
    exact_candidates: list[str],
    contains_any: list[str],
    prefer_contains: list[str] | None = None,
    exclude_contains: list[str] | None = None,
    sj_div_in: set[str] | None = None,
) -> float | None:
    """당기순이익/영업이익처럼, 기업마다 계정명에 붙는 접두/접미 표현이 크게 갈리는
    계정을 찾는다.

    문제 배경: 실제 DART 응답을 확인해보면(진단용 debug-raw-accounts 엔드포인트로
    직접 검증함) 같은 개념이라도 회사마다 계정명이 상당히 다르다.
        - 적자 기업은 "당기순이익" 대신 "당기순손실"로, "영업이익" 대신 "영업손실"로
          완전히 다른 단어를 쓴다(단순히 "(손실)"이 붙는 게 아니다 - 예: 파두 440110).
        - 연결재무제표에서는 "당기순이익" 대신 "당기연결순이익"처럼 접두어가 붙거나,
          지배기업 귀속분만 "지배기업의 소유주에게 귀속되는 당기순이익(손실)"처럼 긴
          수식어가 붙기도 한다(예: RFHIC 218410).
    기존의 정확히 일치(in candidates)하는 방식은 위와 같은 실제 표기 다양성을
    못 따라가 값이 있는데도 "데이터 없음"으로 잘못 판정하는 경우가 많았다
    (PER이 계산 가능한데도 N/A로 나오는 주된 원인 중 하나).

    이 함수는 1) 기존 정확 일치를 그대로 우선 시도하고(기존 동작 유지),
    2) 실패하면 contains_any 핵심 단어(예: "당기순이익"/"당기순손실")가 포함된
    행들만 후보로 추리고, 그 후보들 중에서 3) "지배기업 소유주 귀속분"처럼 EPS
    계산에 맞는 계정을 우선하며, 4) 없으면 후보 중 첫 행을 사용한다. "총포괄"
    (포괄손익)이나 "비지배지분"(소수주주 귀속분)처럼 EPS 분자로 부적절한 항목은
    명시적으로 제외한다.

    주의(실제로 겪은 버그): prefer_contains를 contains_any와 무관하게 "전체 행"에서
    독립적으로 먼저 검색하면 안 된다. 예를 들어 RFHIC(218410)는 포괄손익계산서에
    "지배기업 소유주지분"이라는, "지배기업"+"소유주"는 포함하지만 당기순이익과
    무관한 행(총포괄손익의 귀속 내역)이 실제 당기순이익 행("지배기업의 소유주에게
    귀속되는 당기순이익(손실)")보다 먼저 나오는데, 이를 독립적으로 먼저 찾으면 전혀
    다른 값이 잘못 선택된다. 그래서 prefer_contains는 반드시 "contains_any도
    만족하는 후보들 중에서" 우선순위를 매기는 데만 사용해야 한다.

    sj_div_in: 검색 대상을 특정 재무제표 구분(예: 손익계산서 "IS"/포괄손익계산서
    "CIS")으로 제한한다. 반드시 지정해야 하는 이유(실제로 겪은 버그): 자본변동표
    (SCE)에도 각 자본 항목의 변동 내역을 나열하며 "지배기업", "소유주", "당기순이익"
    같은 단어가 들어간 행이 존재하는데, 이는 당기 손익계산서 수치가 전혀 아니다.
    sj_div 제한 없이 contains 매칭만 하면 이런 무관한 행이 잘못 선택될 수 있다
    (파두 440110에서 실제로 당기순손실(-762억) 대신 자본변동표의 무관한 양수 값이
    잘못 매칭된 사례로 확인됨). exact_candidates 매칭에도 동일하게 적용된다.
    """

    def _in_scope(row: dict) -> bool:
        return sj_div_in is None or (row.get("sj_div") or "") in sj_div_in

    scoped_rows = [r for r in rows if _in_scope(r)]

    exact = _match_amount(scoped_rows, exact_candidates)
    if exact is not None:
        return exact

    def _amount(row: dict) -> float | None:
        raw = row.get("thstrm_amount", "")
        try:
            return float(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            return None

    def _is_excluded(name: str) -> bool:
        return bool(exclude_contains) and any(term in name for term in exclude_contains)

    # 1단계: contains_any 핵심 단어를 실제로 포함하는 행만 후보로 추린다
    # (순서 보존 - 원본 DART 응답 순서 그대로).
    candidates: list[tuple[str, float]] = []
    for row in scoped_rows:
        name = (row.get("account_nm") or "").strip()
        if _is_excluded(name):
            continue
        if not any(term in name for term in contains_any):
            continue
        value = _amount(row)
        if value is not None:
            candidates.append((name, value))

    if not candidates:
        return None

    # 2단계: 그 후보들 중에서 EPS 분자로 적합한 "지배기업/소유주 귀속분"을 우선한다.
    if prefer_contains:
        for name, value in candidates:
            if any(term in name for term in prefer_contains):
                return value

    return candidates[0][1]


def _match_depreciation_amortization(rows: list[dict]) -> float | None:
    """감가상각비(D&A)를 조회한다. 합산 계정이 있으면 그걸 쓰고, 없으면
    유형자산감가상각비+무형자산상각비를 합산한다(둘 다 있으면 이중 계산을 피하기 위해
    합산 계정을 우선한다).
    """
    combined = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["depreciation_amortization"])
    if combined is not None:
        return combined
    return _sum_amounts(rows, _DEPRECIATION_BREAKDOWN_CANDIDATES)


def _fetch_shares_outstanding(corp_code: str, bsns_year: int, api_key: str) -> float | None:
    """발행주식수(보통주) 조회 - PER/PBR 계산(EPS/BPS)에 필요 (요구사항 74).

    재무제표 계정이 아닌 DART의 별도 API(주식의 총수 현황)를 사용한다.
    응답 행 구성/필드명이 기업마다 다소 다를 수 있어 관대하게 파싱하며,
    값을 확정할 수 없으면 숫자를 억지로 만들지 않고 None(추후 N/A 처리)을 반환한다.
    """
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bsns_year": str(bsns_year),
        "reprt_code": "11011",
    }
    try:
        resp = httpx.get(DART_SHARES_ENDPOINT, params=params, timeout=15.0)
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("DART 주식총수 조회 실패(%s, %s): %s", corp_code, bsns_year, exc)
        return None

    if payload.get("status") != "000":
        return None

    rows = payload.get("list", [])
    # 대부분 기업은 "보통주"로 구분 표기하지만, 실제 응답을 확인해보면(진단용
    # debug-raw-accounts로 검증함) 우선주가 없는 일부 기업(예: 셀트리온 068270)은
    # "보통주" 대신 "의결권 있는 주식"으로만 구분해 공시한다. "보통주"를 우선 찾고,
    # 없으면 "의결권 있는 주식"으로 재시도한다(우선주를 제외한 EPS 분모로는 둘 다
    # 동일한 의미다 - 우선주가 있는 기업이면 "의결권 있는 주식"에 우선주가 섞여 있을
    # 수 있으나, 그 경우 대부분 "보통주" 표기가 존재해 위 우선순위로 걸러진다).
    for target in ("보통주", "의결권 있는 주식"):
        for row in rows:
            se = (row.get("se") or "").strip()
            if target not in se:
                continue
            for field in ("istc_totqy", "now_to_isu_stock_totqy"):
                raw = row.get(field)
                if raw and raw != "-":
                    try:
                        return float(str(raw).replace(",", ""))
                    except (ValueError, TypeError):
                        continue
    return None


class DartFinancialProvider(FinancialStatementProvider):
    name = "opendart"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.dart_api_key

    def debug_raw_rows(self, ticker: str, bsns_year: int) -> ProviderResult:
        """[임시 진단용] DART가 실제로 반환하는 계정명(account_nm)/sj_div 원본 목록을 그대로 보여준다.

        PER/EV-EBITDA가 상당수 기업에서 N/A로 나오는 문제의 원인이 "계정명 후보 매핑이
        실제 공시 계정명과 다르다"인지 확인하기 위한 일회성 진단 도구. 문제 원인을 특정한
        뒤 제거할 예정이다.
        """
        if not self._api_key:
            return ProviderResult(status="unavailable", source_name=self.name, message="DART_API_KEY 없음")
        corp_code = get_corp_code(ticker, self._api_key)
        if not corp_code:
            return ProviderResult(status="unavailable", source_name=self.name, message=f"corp_code 없음: {ticker}")

        params = {
            "crtfc_key": self._api_key,
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": "11011",
            "fs_div": "CFS",
        }
        try:
            resp = httpx.get(DART_FINANCIAL_ENDPOINT, params=params, timeout=15.0)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            return ProviderResult(status="error", source_name=self.name, message=str(exc))

        used_fs_div = "CFS"
        if payload.get("status") != "000":
            params["fs_div"] = "OFS"
            used_fs_div = "OFS"
            try:
                resp = httpx.get(DART_FINANCIAL_ENDPOINT, params=params, timeout=15.0)
                resp.raise_for_status()
                payload = resp.json()
            except httpx.HTTPError as exc:
                return ProviderResult(status="error", source_name=self.name, message=str(exc))

        if payload.get("status") != "000":
            return ProviderResult(
                status="empty", source_name=self.name, message=f"DART status={payload.get('status')} {payload.get('message')}"
            )

        rows = payload.get("list", [])
        simplified = [
            {
                "sj_div": r.get("sj_div"),
                "account_nm": r.get("account_nm"),
                "thstrm_amount": r.get("thstrm_amount"),
                "fs_div": r.get("fs_div"),
                "ord": r.get("ord"),
            }
            for r in rows
        ]

        # 발행주식수(보통주) API 원본도 함께 보여준다 - PER/PBR용 EPS/BPS가 못 나오는
        # 기업 중 일부는 재무제표가 아니라 이 별도 API에서 실패하는 경우가 있어서다.
        shares_params = {
            "crtfc_key": self._api_key,
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": "11011",
        }
        shares_raw: object = None
        try:
            shares_resp = httpx.get(DART_SHARES_ENDPOINT, params=shares_params, timeout=15.0)
            shares_resp.raise_for_status()
            shares_payload = shares_resp.json()
            shares_raw = shares_payload
        except httpx.HTTPError as exc:
            shares_raw = {"error": str(exc)}

        parsed_shares = _fetch_shares_outstanding(corp_code, bsns_year, self._api_key)

        # [임시 진단용] get_financial_statements()와 완전히 동일한 인자로 _match_flexible을
        # 직접 호출해본 결과를 함께 보여준다 - 실제 저장되는 값과 이 결과가 다르다면
        # 코드 배포/리로드 문제(예: uvicorn 리로드 지연)를 의심할 수 있는 근거가 된다.
        _INCOME_STATEMENT_DIVS_DEBUG = {"IS", "CIS"}
        parsed_operating_income = _match_flexible(
            rows,
            exact_candidates=ACCOUNT_NAME_CANDIDATES["operating_income"],
            contains_any=["영업이익", "영업손실"],
            exclude_contains=["총포괄"],
            sj_div_in=_INCOME_STATEMENT_DIVS_DEBUG,
        )
        parsed_net_income = _match_flexible(
            rows,
            exact_candidates=ACCOUNT_NAME_CANDIDATES["net_income"],
            contains_any=_NET_INCOME_CONTAINS_ANY,
            prefer_contains=["지배기업", "소유주"],
            exclude_contains=["총포괄", "비지배"],
            sj_div_in=_INCOME_STATEMENT_DIVS_DEBUG,
        )

        return ProviderResult(
            status="ok",
            data={
                "used_fs_div": used_fs_div,
                "row_count": len(rows),
                "rows": simplified,
                "shares_outstanding_raw": shares_raw,
                "parsed_shares_outstanding": parsed_shares,
                "parsed_operating_income": parsed_operating_income,
                "parsed_net_income": parsed_net_income,
            },
            source_name=self.name,
        )

    def get_financial_statements(self, ticker: str, years: int = 5) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message="DART_API_KEY 가 설정되어 있지 않습니다.",
            )

        corp_code = get_corp_code(ticker, self._api_key)
        if not corp_code:
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message=f"OpenDART에서 종목코드 {ticker}에 대응하는 corp_code를 찾을 수 없습니다.",
            )

        current_year = date.today().year
        statements: list[RawFinancialStatement] = []

        for offset in range(years):
            bsns_year = current_year - offset
            params = {
                "crtfc_key": self._api_key,
                "corp_code": corp_code,
                "bsns_year": str(bsns_year),
                "reprt_code": "11011",  # 사업보고서(연간)
                "fs_div": "CFS",  # 연결재무제표, 없으면 OFS(별도)로 재시도
            }
            try:
                resp = httpx.get(DART_FINANCIAL_ENDPOINT, params=params, timeout=15.0)
                resp.raise_for_status()
                payload = resp.json()
            except httpx.HTTPError as exc:
                logger.warning("DART 재무제표 조회 실패(%s, %s): %s", ticker, bsns_year, exc)
                continue

            if payload.get("status") != "000":
                # 연결재무제표 없으면 별도재무제표로 재시도
                params["fs_div"] = "OFS"
                try:
                    resp = httpx.get(DART_FINANCIAL_ENDPOINT, params=params, timeout=15.0)
                    resp.raise_for_status()
                    payload = resp.json()
                except httpx.HTTPError:
                    continue

            if payload.get("status") != "000":
                continue

            rows = payload.get("list", [])
            revenue = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["revenue"])
            # 영업이익/당기순이익은 적자 기업이 "영업손실"/"당기순손실"처럼 아예 다른
            # 단어를 쓰거나, 연결재무제표에서 "당기연결순이익"/"지배기업의 소유주에게
            # 귀속되는 당기순이익(손실)"처럼 접두/수식어가 붙는 경우가 많아, 정확히
            # 일치하는 후보만으로는 실제 존재하는 데이터도 놓치는 경우가 많았다
            # (_match_flexible 참고 - PER이 계산 가능한데도 N/A로 나오던 주된 원인).
            # sj_div_in으로 손익계산서(IS)/포괄손익계산서(CIS)로만 검색 범위를 제한한다.
            # 제한하지 않으면 자본변동표(SCE)에 있는 "지배기업"/"소유주"/"당기순이익"
            # 문구가 포함된 무관한 행이 잘못 매칭될 수 있다(파두 440110에서 실제로
            # 발생 확인 - 아래 _match_flexible 독스트링 참고).
            _INCOME_STATEMENT_DIVS = {"IS", "CIS"}
            operating_income = _match_flexible(
                rows,
                exact_candidates=ACCOUNT_NAME_CANDIDATES["operating_income"],
                contains_any=["영업이익", "영업손실"],
                exclude_contains=["총포괄"],
                sj_div_in=_INCOME_STATEMENT_DIVS,
            )
            net_income = _match_flexible(
                rows,
                exact_candidates=ACCOUNT_NAME_CANDIDATES["net_income"],
                contains_any=_NET_INCOME_CONTAINS_ANY,
                # EPS 분자로는 지배기업(모회사) 소유주 귀속분이 맞다 - 비지배지분까지
                # 합친 연결 총계나, 포괄손익 항목을 섞어 쓰면 안 된다.
                prefer_contains=["지배기업", "소유주"],
                exclude_contains=["총포괄", "비지배"],
                sj_div_in=_INCOME_STATEMENT_DIVS,
            )
            assets = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["assets"])
            liabilities = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["liabilities"])
            equity = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["equity"])
            current_assets = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["current_assets"])
            current_liabilities = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["current_liabilities"])
            inventory = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["inventory"])
            cash_and_equivalents = _match_amount(rows, ACCOUNT_NAME_CANDIDATES["cash_and_equivalents"])
            depreciation_amortization = _match_depreciation_amortization(rows)
            total_borrowings = _sum_amounts(rows, _BORROWINGS_CANDIDATES)
            # 감가상각비를 못 찾았을 때만 의미가 있는 EBITDA 추정 fallback 재료
            non_cash_adjustments_total = _match_amount(rows, _NON_CASH_ADJUSTMENTS_CANDIDATES, sj_div="CF")

            # 사업보고서는 통상 다음 해 3월경 공시됨 -> available_at 근사치
            available_at = date(bsns_year + 1, 4, 1)

            shares_outstanding = _fetch_shares_outstanding(corp_code, bsns_year, self._api_key)

            statements.append(
                RawFinancialStatement(
                    period=f"{bsns_year}FY",
                    reported_at=date(bsns_year, 12, 31),
                    available_at=available_at,
                    revenue=revenue,
                    operating_income=operating_income,
                    net_income=net_income,
                    assets=assets,
                    liabilities=liabilities,
                    equity=equity,
                    operating_cash_flow=None,  # TODO: 현금흐름표 API(fnlttCashflow) 연동
                    free_cash_flow=None,
                    capital_expenditure=None,
                    shares_outstanding=shares_outstanding,
                    current_assets=current_assets,
                    current_liabilities=current_liabilities,
                    inventory=inventory,
                    interest_expense=None,  # TODO: 손익계산서 세부 계정 매핑 보강
                    depreciation_amortization=depreciation_amortization,
                    cash_and_equivalents=cash_and_equivalents,
                    total_borrowings=total_borrowings,
                    non_cash_adjustments_total=non_cash_adjustments_total,
                )
            )

        if not statements:
            return ProviderResult(status="empty", source_name=self.name, data=[])

        return ProviderResult(
            status="ok",
            data=statements,
            source_name=self.name,
            source_url="https://opendart.fss.or.kr/",
            retrieved_at=datetime.utcnow(),
        )


def get_financial_provider() -> FinancialStatementProvider:
    return DartFinancialProvider()
