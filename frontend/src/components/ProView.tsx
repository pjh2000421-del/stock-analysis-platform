"use client";

import { useEffect, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import { FundamentalTable } from "@/components/FundamentalTable";
import { PeerComparisonTable } from "@/components/PeerComparisonTable";
import { ScoreCard } from "@/components/ScoreCard";
import type {
  CompanyDetail,
  CompanyMetricsResponse,
  CompositeScoreResponse,
  PeerComparisonResponse,
} from "@/types/api";

/**
 * Pro View (요구사항 58 순서):
 * Valuation -> Growth -> Profitability -> Financial Health -> Peer Comparison
 * (Historical Valuation은 다음 Phase 확장 예정)
 */
export function ProView({ ticker, company }: { ticker: string; company?: CompanyDetail | null }) {
  const { t } = useTranslation();
  const [metrics, setMetrics] = useState<CompanyMetricsResponse | null>(null);
  const [score, setScore] = useState<CompositeScoreResponse | null>(null);
  // undefined = 아직 조회 중, null = 조회 완료했지만 실패/데이터 없음
  const [peers, setPeers] = useState<PeerComparisonResponse | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setMetrics(null);
    setScore(null);
    setPeers(undefined);
    setError(null);
    Promise.all([api.getCompanyMetrics(ticker), api.getCompanyScore(ticker)])
      .then(([m, s]) => {
        if (!cancelled) {
          setMetrics(m);
          setScore(s);
        }
      })
      .catch((e) => !cancelled && setError(e.message));
    // Peer Comparison은 동종업체 재무데이터를 추가로 계산해야 해서 다소 느릴 수 있으므로
    // 핵심 지표(metrics/score)와 분리하여 별도로 로드한다 (Progressive Loading, 요구사항 65).
    api
      .getCompanyPeers(ticker)
      .then((p) => !cancelled && setPeers(p))
      .catch(() => !cancelled && setPeers(null));
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  if (error) return <p className="text-sm text-negative">{t("common.error")}</p>;

  // 데이터가 아직 로딩 중이어도 표/카드 틀은 즉시 렌더링하고, 각 컴포넌트 내부에서
  // 자체적으로 로딩 상태(뼈대 + "불러오는 중" 메세지)를 표시한다.
  return (
    <div className="space-y-4">
      {company && <ClassificationInfoPanel company={company} />}

      <ScoreCard score={score} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <FundamentalTable
          title={t("valuation.title")}
          rows={
            metrics
              ? [
                  { labelKey: "valuation.per", glossaryKey: "per", value: metrics.valuation.per, suffix: "x" },
                  { labelKey: "valuation.pbr", glossaryKey: "pbr", value: metrics.valuation.pbr, suffix: "x" },
                  { labelKey: "valuation.psr", glossaryKey: "psr", value: metrics.valuation.psr, suffix: "x" },
                  {
                    labelKey: "valuation.evEbitda",
                    glossaryKey: "evEbitda",
                    value: metrics.valuation.ev_ebitda,
                    suffix: "x",
                  },
                ]
              : null
          }
        />
        <FundamentalTable
          title={t("profitability.title")}
          rows={
            metrics
              ? [
                  { labelKey: "profitability.roe", glossaryKey: "roe", value: metrics.profitability.roe, suffix: "%" },
                  { labelKey: "profitability.roa", glossaryKey: "roa", value: metrics.profitability.roa, suffix: "%" },
                  {
                    labelKey: "profitability.operatingMargin",
                    glossaryKey: "operatingMargin",
                    value: metrics.profitability.operating_margin,
                    suffix: "%",
                  },
                  {
                    labelKey: "profitability.netMargin",
                    glossaryKey: "netMargin",
                    value: metrics.profitability.net_margin,
                    suffix: "%",
                  },
                ]
              : null
          }
        />
        <FundamentalTable
          title={t("growth.title")}
          rows={
            metrics
              ? [
                  {
                    labelKey: "growth.revenueGrowthYoy",
                    glossaryKey: "revenueGrowthYoy",
                    value: metrics.growth.revenue_growth_yoy,
                    suffix: "%",
                  },
                  { labelKey: "growth.epsGrowthYoy", value: metrics.growth.eps_growth_yoy, suffix: "%" },
                  {
                    labelKey: "growth.operatingIncomeGrowthYoy",
                    value: metrics.growth.operating_income_growth_yoy,
                    suffix: "%",
                  },
                ]
              : null
          }
        />
        <FundamentalTable
          title={t("financialHealth.title")}
          rows={
            metrics
              ? [
                  {
                    labelKey: "financialHealth.debtEquity",
                    glossaryKey: "debtEquity",
                    value: metrics.financial_health.debt_equity,
                    suffix: "%",
                  },
                  {
                    labelKey: "financialHealth.currentRatio",
                    glossaryKey: "currentRatio",
                    value: metrics.financial_health.current_ratio,
                    suffix: "%",
                  },
                  {
                    labelKey: "financialHealth.interestCoverage",
                    glossaryKey: "interestCoverage",
                    value: metrics.financial_health.interest_coverage,
                    suffix: "x",
                  },
                ]
              : null
          }
        />
      </div>

      <PeerComparisonTable data={peers} />
    </div>
  );
}

/**
 * 업종 분류 출처 투명성 패널 (요구사항 15).
 * 어떤 분류체계(WICS 등)에서, 어느 출처로, 언제 분류를 가져왔는지 Pro View에서
 * 바로 확인할 수 있게 해서, 나중에 다시 잘못된 업종이 나타나더라도 원인을
 * 즉시 추적할 수 있게 한다. investment_industry가 아직 없는 경우에는 그 사실을
 * 그대로 보여주고, raw_industry를 대신 표시하지 않는다.
 */
function ClassificationInfoPanel({ company }: { company: CompanyDetail }) {
  const { t } = useTranslation();
  const classification = company.classification;
  const raw = company.raw_classification;

  const updatedAt = classification?.updated_at
    ? new Date(classification.updated_at).toISOString().slice(0, 10)
    : null;

  return (
    <div className="rounded border border-gray-200 bg-gray-50 p-4 text-sm">
      <h3 className="mb-2 font-semibold text-gray-700">{t("classification.title")}</h3>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
        <div className="flex justify-between sm:justify-start sm:gap-2">
          <dt className="text-gray-400">{t("classification.investmentIndustry")}</dt>
          <dd className="font-medium text-gray-700">
            {classification?.industry ?? t("classification.unknown")}
          </dd>
        </div>
        <div className="flex justify-between sm:justify-start sm:gap-2">
          <dt className="text-gray-400">{t("classification.system")}</dt>
          <dd className="text-gray-600">{classification?.system ?? "-"}</dd>
        </div>
        <div className="flex justify-between sm:justify-start sm:gap-2 sm:col-span-2">
          <dt className="text-gray-400">{t("classification.source")}</dt>
          <dd className="break-all text-gray-600">{classification?.source ?? "-"}</dd>
        </div>
        <div className="flex justify-between sm:justify-start sm:gap-2">
          <dt className="text-gray-400">{t("classification.updatedAt")}</dt>
          <dd className="text-gray-600">{updatedAt ?? "-"}</dd>
        </div>
        <div className="flex justify-between sm:justify-start sm:gap-2">
          <dt className="text-gray-400">{t("classification.confidence")}</dt>
          <dd className="text-gray-600">
            {classification?.confidence != null ? `${Math.round(classification.confidence * 100)}%` : "-"}
          </dd>
        </div>
      </dl>
      {raw?.industry && (
        <div className="mt-3 border-t border-gray-200 pt-2 text-xs text-gray-400">
          <span className="font-medium text-gray-500">{t("classification.rawIndustry")}: </span>
          {raw.industry}
          <div className="mt-0.5">{t("classification.rawNote")}</div>
        </div>
      )}
    </div>
  );
}
