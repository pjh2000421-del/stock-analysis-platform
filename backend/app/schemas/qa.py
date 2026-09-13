"""종목 데이터 기반 AI 질의응답(Q&A) 스키마 (요구사항: AI QA)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class AskQuestionResponse(BaseModel):
    ticker: str
    question: str
    answer: str | None = None
    # AI 서비스 자체를 사용할 수 없는 경우(API Key 미설정 등) True.
    # 요청은 정상 처리되었으나 일시적으로 답변을 생성하지 못한 경우(API 오류 등)와 구분한다.
    is_unavailable: bool = False
    message: str | None = None
    model: str | None = None
    disclaimer: str = "AI가 제공된 종목 데이터를 바탕으로 생성한 답변이며, 투자 조언이 아닙니다."
