"""
거시경제/시장 지수 Provider Adapter (요구사항 26).

지수/환율: FinanceDataReader로 조회 가능 (KS11=KOSPI, KQ11=KOSDAQ, USD/KRW 등).
CPI(물가): 한국은행 ECOS Open API(StatisticSearch)를 사용한다. 통계표코드 "901Y009"
(소비자물가지수, 2020=100 기준), 항목코드 "0"(총지수), 주기 "M"(월)로 조회한다.

ECOS는 월별 지수만 제공하므로(연간 시계열이 따로 없음), adjust_for_inflation()이
기대하는 {연도: CPI} 형태로 쓰기 위해 같은 연도의 월별 지수를 산술평균해 연간 CPI로
근사한다 - 관행적으로 연간 CPI를 "그 해 월별 지수의 평균"으로 계산하는 것과 동일한
방식이다. ECOS_API_KEY가 없거나 API 호출이 실패하면 "unavailable"/"error"로 처리하고,
물가조정 로직(event_analysis.inflation_adjustment)은 CPI 데이터가 없을 때 nominal
금액만 표시하도록 이미 graceful하게 처리되어 있다(요구사항 74 - 숫자를 함부로 만들지
않는다).
"""
from __future__ import annotations

from datetime import date, datetime

import httpx

from app.core.config import get_settings
from app.core.errors import ProviderUnavailableError
from app.core.logging import get_logger
from app.providers.base import MacroDataProvider, ProviderResult

logger = get_logger(__name__)

ECOS_STATISTIC_SEARCH_ENDPOINT = "https://ecos.bok.or.kr/api/StatisticSearch"
ECOS_CPI_STAT_CODE = "901Y009"  # 소비자물가지수(2020=100)
ECOS_CPI_ITEM_CODE = "0"  # 총지수(전체 품목)


class FinanceDataReaderMacroProvider(MacroDataProvider):
    name = "finance_datareader_macro"

    def _import_fdr(self):
        try:
            import FinanceDataReader as fdr  # type: ignore

            return fdr
        except ImportError as exc:
            raise ProviderUnavailableError(self.name, "finance-datareader 미설치") from exc

    def get_market_index(self, index_code: str, start: date, end: date) -> ProviderResult:
        try:
            fdr = self._import_fdr()
            df = fdr.DataReader(index_code, start, end)
        except ProviderUnavailableError as exc:
            return ProviderResult(status="unavailable", message=str(exc), source_name=self.name)
        except Exception as exc:  # noqa: BLE001
            logger.exception("시장 지수 조회 실패: %s", index_code)
            return ProviderResult(status="error", message=str(exc), source_name=self.name)

        if df is None or df.empty:
            return ProviderResult(status="empty", source_name=self.name)

        return ProviderResult(
            status="ok",
            data=df,
            source_name=self.name,
            retrieved_at=datetime.utcnow(),
        )

    def get_fx_rate(self, pair: str, start: date, end: date) -> ProviderResult:
        try:
            fdr = self._import_fdr()
            df = fdr.DataReader(pair, start, end)
        except ProviderUnavailableError as exc:
            return ProviderResult(status="unavailable", message=str(exc), source_name=self.name)
        except Exception as exc:  # noqa: BLE001
            logger.exception("환율 조회 실패: %s", pair)
            return ProviderResult(status="error", message=str(exc), source_name=self.name)

        if df is None or df.empty:
            return ProviderResult(status="empty", source_name=self.name)

        return ProviderResult(status="ok", data=df, source_name=self.name, retrieved_at=datetime.utcnow())

    def get_cpi(self, start: date, end: date) -> ProviderResult:
        """소비자물가지수를 연도별 평균으로 조회한다. 반환 data는 {연도: CPI} dict.

        ECOS StatisticSearch URL 형식(공식 문서 기준):
        /api/StatisticSearch/{인증키}/{요청유형}/{언어구분}/{요청시작건수}/{요청종료건수}/
        {통계표코드}/{주기}/{검색시작일자}/{검색종료일자}/{통계항목코드1}
        """
        settings = get_settings()
        api_key = settings.ecos_api_key
        if not api_key:
            return ProviderResult(
                status="unavailable",
                source_name="ecos_bok",
                message="ECOS_API_KEY 가 설정되어 있지 않습니다.",
            )

        start_ym = f"{start.year}{start.month:02d}"
        end_ym = f"{end.year}{end.month:02d}"
        # 요청시작/종료건수는 결과 건수 페이징 값이다 - 최대 몇 년치를 조회하든 월별 데이터가
        # 수백 건을 넘길 일은 없으므로(수십 년치라도 수백 건 수준) 넉넉히 1000으로 고정한다.
        url = (
            f"{ECOS_STATISTIC_SEARCH_ENDPOINT}/{api_key}/json/kr/1/1000/"
            f"{ECOS_CPI_STAT_CODE}/M/{start_ym}/{end_ym}/{ECOS_CPI_ITEM_CODE}"
        )

        try:
            resp = httpx.get(url, timeout=15.0)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("ECOS CPI 조회 연결 실패: %s", exc)
            return ProviderResult(status="error", source_name="ecos_bok", message="ECOS API 연결에 실패했습니다.")
        except ValueError:
            return ProviderResult(status="error", source_name="ecos_bok", message="ECOS 응답 파싱 실패")

        # ECOS는 정상 데이터가 아니면(인증 실패, 데이터 없음 등) 최상위를 "RESULT" 키로
        # 감싸서 응답한다(예: {"RESULT": {"CODE": "ERROR-100", "MESSAGE": "인증키가 유효하지
        # 않습니다."}}). 정상 응답은 "StatisticSearch" 키를 최상위로 사용한다.
        if "RESULT" in payload:
            result = payload.get("RESULT") or {}
            code = str(result.get("CODE", ""))
            message = result.get("MESSAGE") or "ECOS 조회 오류"
            status = "empty" if code.startswith("INFO") else "error"
            logger.warning("ECOS CPI 응답 오류(%s): %s", code, message)
            return ProviderResult(status=status, source_name="ecos_bok", message=message)

        rows = (payload.get("StatisticSearch") or {}).get("row") or []
        if not rows:
            return ProviderResult(status="empty", source_name="ecos_bok")

        monthly_by_year: dict[int, list[float]] = {}
        for row in rows:
            time_str = row.get("TIME") or ""
            value_str = row.get("DATA_VALUE")
            if len(time_str) < 4 or value_str in (None, ""):
                continue
            try:
                year = int(time_str[:4])
                value = float(value_str)
            except (ValueError, TypeError):
                continue
            monthly_by_year.setdefault(year, []).append(value)

        if not monthly_by_year:
            return ProviderResult(status="empty", source_name="ecos_bok")

        annual_cpi = {year: sum(values) / len(values) for year, values in monthly_by_year.items()}

        return ProviderResult(
            status="ok",
            data=annual_cpi,
            source_name="ecos_bok",
            source_url="https://ecos.bok.or.kr/api/",
            retrieved_at=datetime.utcnow(),
        )


def get_macro_provider() -> MacroDataProvider:
    return FinanceDataReaderMacroProvider()
