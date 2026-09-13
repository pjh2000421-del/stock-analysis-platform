"""
OpenDART 공통 유틸리티: corp_code(고유번호) 매핑 캐시.

OpenDART는 종목코드(ticker)가 아닌 자체 corp_code로 기업을 식별하므로,
전체 corp_code 목록(zip)을 최초 1회 다운로드하여 로컬에 캐시한다.
(전 종목 상세 데이터를 저장하는 것이 아니라 검색을 위한 코드 매핑표이므로
 요구사항 3의 "전 종목 데이터 사전 다운로드 금지"와는 별개의 가벼운 메타데이터이다.)
"""
from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_FILE = CACHE_DIR / "dart_corp_codes.json"

CORP_CODE_ENDPOINT = "https://opendart.fss.or.kr/api/corpCode.xml"


def _download_corp_codes(api_key: str) -> dict[str, str]:
    """stock_code -> corp_code 매핑을 다운로드하여 캐시 파일에 저장한다."""
    resp = httpx.get(CORP_CODE_ENDPOINT, params={"crtfc_key": api_key}, timeout=30.0)
    resp.raise_for_status()

    mapping: dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("CORPCODE.xml") as f:
            tree = ET.parse(f)
            for node in tree.getroot().findall("list"):
                stock_code = (node.findtext("stock_code") or "").strip()
                corp_code = (node.findtext("corp_code") or "").strip()
                if stock_code:
                    mapping[stock_code] = corp_code

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return mapping


def download_full_listed_companies(api_key: str) -> list[dict[str, str]]:
    """DART corpCode.xml 전체에서 stock_code(종목코드)가 있는 항목(=실제 상장기업)만
    뽑아 (stock_code, corp_name, corp_code) 리스트로 반환한다.

    DART는 스크래핑이 아닌 정식 공개 API라, KRX 웹 소스가 해외 리전 서버에서
    막히는 것과 달리 지역 제한 없이 안정적으로 동작할 가능성이 높다. 전체 상장사
    마스터 목록(종목코드/기업명)을 대체 소스로 확보하기 위한 용도.
    """
    resp = httpx.get(CORP_CODE_ENDPOINT, params={"crtfc_key": api_key}, timeout=30.0)
    resp.raise_for_status()

    listed: list[dict[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open("CORPCODE.xml") as f:
            tree = ET.parse(f)
            for node in tree.getroot().findall("list"):
                stock_code = (node.findtext("stock_code") or "").strip()
                corp_name = (node.findtext("corp_name") or "").strip()
                corp_code = (node.findtext("corp_code") or "").strip()
                if stock_code and corp_name:
                    listed.append({"stock_code": stock_code, "corp_name": corp_name, "corp_code": corp_code})
    return listed


def get_corp_code(ticker: str, api_key: str) -> str | None:
    """캐시에서 corp_code를 조회하고, 없으면 최초 1회 다운로드 후 캐시한다."""
    mapping: dict[str, str] = {}
    if CACHE_FILE.exists():
        try:
            mapping = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            mapping = {}

    if ticker not in mapping:
        try:
            mapping = _download_corp_codes(api_key)
        except Exception:  # noqa: BLE001
            logger.exception("DART corp_code 목록 다운로드 실패")
            return None

    return mapping.get(ticker)
