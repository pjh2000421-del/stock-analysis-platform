"""
FICS(FnGuide Industry Classification Standard) Provider.

TODO: FICS는 WICS와 마찬가지로 FnGuide가 관리하는 분류체계이지만, WICS(wiseindex.com)와
달리 무료로 접근 가능한 공개 API/데이터소스를 확인하지 못했다(유료 데이터 서비스로만
제공되는 것으로 보인다). 인터페이스만 준비해두고 실제 데이터가 확보되기 전까지는 항상
unavailable을 반환해 다음 우선순위(KRX 원본/DART)로 넘어가게 한다. 임의로 값을
만들어내지 않는다(요구사항 4, 17).
"""
from __future__ import annotations

from app.providers.base import ClassificationProvider, ProviderResult


class FicsClassificationProvider(ClassificationProvider):
    name = "fics"

    def get_classification(self, ticker: str) -> ProviderResult:
        return ProviderResult(
            status="unavailable",
            source_name=self.name,
            message="FICS는 현재 무료로 접근 가능한 데이터소스를 확인하지 못해 미구현 상태입니다(TODO).",
        )


def get_fics_provider() -> FicsClassificationProvider:
    return FicsClassificationProvider()
