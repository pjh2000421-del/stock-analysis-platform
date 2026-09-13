"""
업종 동종기업 비교 (Peer Comparison) Service.

요구사항: "업종 대비 상대 밸류에이션" - PER/PBR/EV-EBITDA/ROE를 같은 업종
기업들과 비교하는 표 + 업종 중앙값 대비 할인율/프리미엄(%)을 제공한다.

동종업체 판단 기준(중요, 개편됨): 예전에는 Company.industry(KRX 상장법인목록 KSIC
기반 세부 업종 텍스트, 예: "방송장비 및 전자기기")로 동종업체를 매칭했으나, 이는
투자분석 관점에서 너무 broad/legal한 분류라 부적절했다(예: 삼성전자가 "방송장비 및
전자기기"로 묶이는 문제). 이제는 Company.investment_industry(WICS 등 투자용
분류, 예: "반도체와반도체장비")를 기준으로 매칭한다. Company.raw_industry(옛
industry)는 DB 쿼리 부담을 줄이기 위한 1차 후보군 선별에만 보조적으로 사용하고,
최종 동종업체 판정은 반드시 investment_industry 일치 여부로 확정한다
(raw_industry만으로 최종 판단하지 않는다).

주의: Company.sector 컬럼은 업종이 아니라 KRX의 시장 소속부/구분(예: "우량기업부",
"벤처기업부" 등) 정보라서 서로 다른 업종의 대형주끼리도 같은 소속부로 묶여버리는
문제가 있었다(예: SK하이닉스-반도체 vs 두산에너빌리티-기계 제조가 둘 다 "nan"으로
저장되어 동종업체로 잘못 묶인 사례). 그래서 동종업체 매칭에 sector는 사용하지 않는다.

주의(Lazy Loading 원칙, 요구사항 3):
- 전체 종목의 재무데이터/업종분류를 미리 계산해두지 않는다.
- 같은 investment_industry로 분류된 기업 중 시가총액 상위 N개만 골라, 그 기업들의
  재무지표를 (이미 캐시되어 있으면 재사용하고, 없으면 그때 계산해서) 비교 대상으로
  사용한다. investment_industry가 아직 채워지지 않은 후보는 raw_industry가 같은
  기업 중에서만 그때 분류를 계산해 재확인한다(전체 종목을 일괄 분류하지 않는다).
"""
from __future__ import annotations

import statistics

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.company import Company
from app.schemas.financial import PeerComparisonResponse, PeerComparisonRow
from app.services.classification_service import ensure_classification
from app.services.price_service import ensure_price_history
from app.services.scoring_service import get_latest_metric

logger = get_logger(__name__)

MAX_PEERS = 4
MAX_RAW_CANDIDATES = MAX_PEERS * 5  # investment_industry 재확인용 1차 후보 pool 크기
METRIC_KEYS = ("per", "pbr", "ev_ebitda", "roe")


def _find_peer_companies(db: Session, company: Company) -> list[Company]:
    """investment_industry가 일치하는 동종업체를 찾는다 (raw_industry는 후보군 선별에만 사용)."""
    peers = list(
        db.execute(
            select(Company)
            .where(
                Company.investment_industry == company.investment_industry,
                Company.ticker != company.ticker,
                Company.market_cap.is_not(None),
            )
            .order_by(Company.market_cap.desc())
            .limit(MAX_PEERS)
        )
        .scalars()
        .all()
    )
    if len(peers) >= MAX_PEERS or not company.raw_industry:
        return peers

    # 아직 investment_industry가 계산되지 않은 기업이 있을 수 있으므로, 같은
    # raw_industry(KRX 원본) 후보군에서 추가로 분류를 시도해 실제로 investment_industry가
    # 일치하는지 재확인한다. 최종 판정은 항상 investment_industry 기준이다.
    seen = {p.ticker for p in peers}
    extra_pool = list(
        db.execute(
            select(Company)
            .where(
                Company.raw_industry == company.raw_industry,
                Company.ticker != company.ticker,
                Company.market_cap.is_not(None),
            )
            .order_by(Company.market_cap.desc())
            .limit(MAX_RAW_CANDIDATES)
        )
        .scalars()
        .all()
    )
    for candidate in extra_pool:
        if len(peers) >= MAX_PEERS:
            break
        if candidate.ticker in seen:
            continue
        try:
            ensure_classification(db, candidate)
        except Exception:  # noqa: BLE001 - 후보 하나 실패해도 전체 Peer Comparison이 죽으면 안 됨
            logger.exception("동종업체 후보 분류 실패: %s", candidate.ticker)
            continue
        if candidate.investment_industry == company.investment_industry:
            peers.append(candidate)
            seen.add(candidate.ticker)

    # 1차 결과(investment_industry 일치, market_cap desc)와 2차 fallback 결과(raw_industry
    # 후보 중 재분류로 확인된 것들, 별도 쿼리로 시가총액 desc 정렬됨)를 합친 뒤에는 두 목록의
    # 정렬 순서가 서로 어긋날 수 있으므로, 최종적으로 다시 한번 시가총액 내림차순으로
    # 정렬해 "동종업체는 항상 시가총액 큰 순서대로" 보이도록 보장한다.
    peers.sort(key=lambda c: c.market_cap or 0, reverse=True)
    return peers


def get_peer_comparison(db: Session, company: Company) -> PeerComparisonResponse:
    ensure_classification(db, company)
    if not company.investment_industry:
        return PeerComparisonResponse(ticker=company.ticker, industry=None, rows=[], discount_premium={})

    peer_companies = _find_peer_companies(db, company)

    rows: list[PeerComparisonRow] = []

    ensure_price_history(db, company, "5D")
    self_metric = get_latest_metric(db, company)
    rows.append(
        PeerComparisonRow(
            label=company.company_name,
            ticker=company.ticker,
            per=self_metric.per,
            per_is_deficit=self_metric.per_is_deficit,
            pbr=self_metric.pbr,
            pbr_is_deficit=self_metric.pbr_is_deficit,
            ev_ebitda=self_metric.ev_ebitda,
            ev_ebitda_is_deficit=self_metric.ev_ebitda_is_deficit,
            ev_ebitda_is_estimated=self_metric.ev_ebitda_is_estimated,
            roe=self_metric.roe,
        )
    )

    peer_values: dict[str, list[float]] = {k: [] for k in METRIC_KEYS}
    for peer in peer_companies:
        try:
            # PER/PBR 계산에는 현재가가 필요한데, 아직 아무도 조회한 적 없는 동종업체는
            # 가격 데이터가 DB에 캐시되어 있지 않을 수 있다 - 짧은 기간만 lazy loading한다.
            ensure_price_history(db, peer, "5D")
            metric = get_latest_metric(db, peer)
        except Exception:  # noqa: BLE001 - 동종업체 하나 실패해도 전체가 깨지면 안 됨
            logger.exception("동종업체 재무지표 계산 실패: %s", peer.ticker)
            continue

        rows.append(
            PeerComparisonRow(
                label=peer.company_name,
                ticker=peer.ticker,
                per=metric.per,
                per_is_deficit=metric.per_is_deficit,
                pbr=metric.pbr,
                pbr_is_deficit=metric.pbr_is_deficit,
                ev_ebitda=metric.ev_ebitda,
                ev_ebitda_is_deficit=metric.ev_ebitda_is_deficit,
                ev_ebitda_is_estimated=metric.ev_ebitda_is_estimated,
                roe=metric.roe,
            )
        )
        for key in METRIC_KEYS:
            value = getattr(metric, key)
            if value is not None:
                peer_values[key].append(value)

    medians: dict[str, float | None] = {
        key: (statistics.median(values) if values else None) for key, values in peer_values.items()
    }
    rows.append(
        PeerComparisonRow(
            label="업종 Median",
            per=medians["per"],
            pbr=medians["pbr"],
            ev_ebitda=medians["ev_ebitda"],
            roe=medians["roe"],
        )
    )

    discount_premium: dict[str, float | None] = {}
    for key in ("per", "pbr", "ev_ebitda"):
        self_value = getattr(self_metric, key)
        median_value = medians[key]
        if self_value is not None and median_value:
            discount_premium[key] = round((self_value - median_value) / median_value * 100, 1)
        else:
            discount_premium[key] = None

    return PeerComparisonResponse(
        ticker=company.ticker,
        industry=company.investment_industry,
        rows=rows,
        discount_premium=discount_premium,
    )
