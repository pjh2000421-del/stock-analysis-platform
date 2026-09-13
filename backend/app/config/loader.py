"""
Config(JSON) 로더.

Score/Similarity weight를 코드에 하드코딩하지 않고 이 디렉토리의 JSON 파일에서
로드한다. (요구사항 11, 25: weight는 config로 관리, 투명하게 공개)
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent


@lru_cache
def load_scoring_weights() -> dict:
    return json.loads((CONFIG_DIR / "scoring_weights.json").read_text(encoding="utf-8"))


@lru_cache
def load_similarity_weights() -> dict:
    return json.loads((CONFIG_DIR / "similarity_weights.json").read_text(encoding="utf-8"))
