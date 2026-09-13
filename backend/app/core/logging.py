"""
공통 logging 설정.

외부 API 호출 실패 등은 여기 설정된 logger로 기록하고,
사용자에게는 core.errors 의 ProviderUnavailableError 등을 통해
이해 가능한 메시지로 변환하여 전달한다. (요구사항 66)
"""
import logging
import sys

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
