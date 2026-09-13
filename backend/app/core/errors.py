"""
공통 예외 클래스.

외부 Provider 실패가 전체 페이지/요청을 깨뜨리지 않도록,
서비스 레이어에서는 아래 예외를 사용해 "정상적인 실패 상태"로 처리한다.
(요구사항 5, 66: Provider unavailable을 정상 상태로 처리)
"""
from __future__ import annotations


class AppError(Exception):
    """애플리케이션 공통 예외"""


class ProviderUnavailableError(AppError):
    """
    외부 데이터 Provider를 사용할 수 없는 경우.
    (API Key 미설정, 인증 실패, 서비스 자체가 아직 계약/승인되지 않은 경우 등)
    전체 요청을 실패시키지 않고, 상위 서비스에서 이 예외를 잡아
    "N/A" 또는 "unavailable" 상태로 변환해 응답한다.
    """

    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"[{provider}] 사용 불가: {reason}")


class ExternalAPIError(AppError):
    """외부 API 호출 중 예상치 못한 오류 (네트워크, 5xx 등)"""

    def __init__(self, provider: str, detail: str):
        self.provider = provider
        self.detail = detail
        super().__init__(f"[{provider}] 호출 오류: {detail}")


class NotFoundError(AppError):
    """조회 대상(기업, 뉴스 등)을 찾을 수 없는 경우"""


class AnalysisDataError(AppError):
    """
    Analysis Lab(app/ml/feature_matrix.py) 파이프라인에서, 사용자가 고른 설정(config)
    조합으로는 정상적으로 학습 데이터를 만들 수 없는 경우 (예: 아직 지원하지 않는
    예측 대상/Feature 조합, 학습에 필요한 최소 거래일 수 미달 등).
    이 예외는 Provider 실패와 달리 "사용자 입력/데이터 상태" 문제이므로,
    analysis_service에서 잡아 AnalysisJob.status="failed"와 함께 사용자가 이해할 수 있는
    error_message로 변환한다 (요구사항 74 - 숫자를 함부로 만들지 않는다는 원칙의 연장).
    """
