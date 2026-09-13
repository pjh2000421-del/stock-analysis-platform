"""
Anthropic(Claude) Chat API Adapter — 종목 데이터 기반 AI 질의응답 기능(요구사항: AI QA).

다른 Provider들과 동일한 패턴(httpx 직접 호출 + ProviderResult 반환)을 따른다.
API Key가 없으면 "unavailable"을 반환해 정상적으로 처리한다(요구사항 5와 동일한 원칙).
"""
from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.base import ProviderResult

logger = get_logger(__name__)

ANTHROPIC_MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicChatProvider:
    """Claude Messages API를 이용한 단발성 질의응답 Provider."""

    name = "anthropic"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.anthropic_api_key
        self._model = settings.anthropic_model

    @property
    def model(self) -> str:
        return self._model

    def ask(self, system_prompt: str, question: str, max_tokens: int = 1024) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(
                status="unavailable",
                source_name=self.name,
                message="ANTHROPIC_API_KEY 가 설정되어 있지 않습니다.",
            )

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": question}],
        }

        try:
            resp = httpx.post(
                ANTHROPIC_MESSAGES_ENDPOINT, headers=headers, json=payload, timeout=30.0
            )
        except httpx.HTTPError as exc:
            logger.warning("Anthropic API 연결 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message="AI 서비스 연결에 실패했습니다.")

        if resp.status_code == 401:
            return ProviderResult(
                status="error", source_name=self.name, message="ANTHROPIC_API_KEY가 유효하지 않습니다."
            )
        if resp.status_code == 429:
            return ProviderResult(
                status="error", source_name=self.name, message="AI 서비스 사용량이 많습니다. 잠시 후 다시 시도해주세요."
            )
        if resp.status_code >= 400:
            logger.warning("Anthropic API 오류(%s): %s", resp.status_code, resp.text[:500])
            return ProviderResult(status="error", source_name=self.name, message="AI 응답 생성 중 오류가 발생했습니다.")

        try:
            data = resp.json()
            text_parts = [block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"]
            answer = "\n".join(part for part in text_parts if part).strip()
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Anthropic API 응답 파싱 실패: %s", exc)
            return ProviderResult(status="error", source_name=self.name, message="AI 응답을 해석할 수 없습니다.")

        if not answer:
            return ProviderResult(status="empty", source_name=self.name, message="AI가 빈 응답을 반환했습니다.")

        return ProviderResult(status="ok", data=answer, source_name=self.name)


def get_llm_provider() -> AnthropicChatProvider:
    return AnthropicChatProvider()
