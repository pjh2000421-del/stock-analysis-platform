"""API 공통 Dependency."""
from app.db.session import get_db  # noqa: F401
from app.models.watchlist import DEMO_USER_ID  # noqa: F401


def get_current_user_id() -> int:
    """
    인증 시스템 도입 전까지 사용하는 데모 사용자 ID.
    (요구사항 54: 향후 Authentication Provider로 교체 용이하게 설계)
    """
    return DEMO_USER_ID
