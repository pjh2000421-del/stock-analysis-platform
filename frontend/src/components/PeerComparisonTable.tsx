"use client";

import Link from "next/link";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import type { PeerComparisonResponse } from "@/types/api";

function fmt(value: number | null, suffix: string): string {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(1)}${suffix}`;
}

/** 값이 낮을수록 "저평가 신호"에 가까운 지표(밸류에이션 계열). 색상 방향을 결정하는 데 쓴다. */
const LOWER_IS_CHEAPER = new Set(["per", "pbr", "ev_ebitda"]);

const METRIC_LABEL_KEY: Record<string, string> = {
  per: "valuation.per",
  pbr: "valuation.pbr",
  ev_ebitda: "valuation.evEbitda",
};

const METRIC_GLOSSARY_KEY: Record<string, string> = {
  per: "per",
  pbr: "pbr",
  ev_ebitda: "evEbitda",
};

/** 업종 Median 대비 %diff 값을 "높음/낮음/비슷" 판정 + 해당 방향의 해설 문구로 변환한다. */
function buildInterpretation(
  metricKey: "per" | "pbr" | "ev_ebitda",
  diffPct: number,
  t: (k: string, f?: string) => string
): { judgmentLabel: string; explanation: string; tone: "cheaper" | "richer" | "neutral" } {
  const SIMILAR_THRESHOLD = 3; // %p 이내 차이는 "업종과 비슷"으로 판정
  const glossaryKey = METRIC_GLOSSARY_KEY[metricKey];

  if (Math.abs(diffPct) < SIMILAR_THRESHOLD) {
    return { judgmentLabel: t("peerComparison.similarToPeers"), explanation: "", tone: "neutral" };
  }
  if (diffPct > 0) {
    return {
      judgmentLabel: t("peerComparison.higherThanPeers"),
      explanation: t(`glossary.${glossaryKey}High`, ""),
      tone: LOWER_IS_CHEAPER.has(metricKey) ? "richer" : "cheaper",
    };
  }
  return {
    judgmentLabel: t("peerComparison.lowerThanPeers"),
    explanation: t(`glossary.${glossaryKey}Low`, ""),
    tone: LOWER_IS_CHEAPER.has(metricKey) ? "cheaper" : "richer",
  };
}

/** 적자/자본잠식으로 값이 없는 경우 배지, 아니면 일반 숫자/N/A 텍스트를 렌더링한다. */
function MetricCell({
  value,
  suffix,
  isDeficit,
  deficitLabel,
  isEstimated,
  estimatedLabel,
}: {
  value: number | null;
  suffix: string;
  isDeficit: boolean;
  deficitLabel: string;
  isEstimated?: boolean;
  estimatedLabel?: string;
}) {
  if (isDeficit) {
    return <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700">{deficitLabel}</span>;
  }
  return (
    <>
      {fmt(value, suffix)}
      {isEstimated && value !== null && value !== undefined && (
        <span className="ml-1 text-xs font-normal text-gray-400">({estimatedLabel})</span>
      )}
    </>
  );
}

/**
 * 업종 동종기업 비교 (Peer Comparison) 표.
 * PER/PBR/EV-EBITDA/ROE를 같은 업종 기업들과 나란히 보여주고,
 * 업종 Median 대비 할인율/프리미엄(%)을 함께 표시한다.
 *
 * data === undefined: 아직 조회 중(로딩) - 카드 틀 + 로딩 메세지만 표시.
 * data === null: 조회는 끝났지만 실패/데이터 없음 - "비교 대상 부족" 메세지 표시.
 */
export function PeerComparisonTable({ data }: { data: PeerComparisonResponse | null | undefined }) {
  const { t } = useTranslation();

  if (data === undefined) {
    return (
      <div className="rounded border border-gray-200 bg-white p-4">
        <h3 className="mb-2 font-semibold text-brand">{t("peerComparison.title")}</h3>
        <p className="text-sm text-gray-400">{t("common.loading")}</p>
      </div>
    );
  }

  if (!data || !data.rows || data.rows.length === 0) {
    return (
      <div className="rounded border border-gray-200 bg-white p-4">
        <h3 className="mb-2 font-semibold text-brand">{t("peerComparison.title")}</h3>
        <p className="text-sm text-gray-400">{t("peerComparison.noPeers")}</p>
      </div>
    );
  }

  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="font-semibold text-brand">{t("peerComparison.title")}</h3>
        {data.industry && <span className="text-xs text-gray-400">{data.industry}</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs text-gray-400">
              <th className="py-2 pr-2 font-normal">기업</th>
              <th className="py-2 pr-2 text-right font-normal">PER</th>
              <th className="py-2 pr-2 text-right font-normal">PBR</th>
              <th className="py-2 pr-2 text-right font-normal">EV/EBITDA</th>
              <th className="py-2 pr-2 text-right font-normal">ROE</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.rows.map((row, i) => {
              const isMedianRow = row.label === "업종 Median";
              return (
                <tr key={i} className={isMedianRow ? "font-medium text-gray-700" : "text-gray-900"}>
                  <td className="py-2 pr-2">
                    {row.ticker ? (
                      <Link href={`/company/${row.ticker}`} className="text-brand hover:underline">
                        {row.label}
                      </Link>
                    ) : (
                      row.label
                    )}
                  </td>
                  <td className="py-2 pr-2 text-right tabular-num">
                    <MetricCell value={row.per} suffix="x" isDeficit={row.per_is_deficit} deficitLabel="적자" />
                  </td>
                  <td className="py-2 pr-2 text-right tabular-num">
                    <MetricCell value={row.pbr} suffix="x" isDeficit={row.pbr_is_deficit} deficitLabel="자본잠식" />
                  </td>
                  <td className="py-2 pr-2 text-right tabular-num">
                    <MetricCell
                      value={row.ev_ebitda}
                      suffix="x"
                      isDeficit={row.ev_ebitda_is_deficit}
                      deficitLabel="적자"
                      isEstimated={row.ev_ebitda_is_estimated}
                      estimatedLabel={t("common.estimated")}
                    />
                  </td>
                  <td className="py-2 pr-2 text-right tabular-num">{fmt(row.roe, "%")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 border-t border-gray-100 pt-3 text-xs text-gray-500">
        <span className="text-gray-400">{t("peerComparison.discountPremium")}:</span>
        {(["per", "pbr", "ev_ebitda"] as const).map((key) => {
          const v = data.discount_premium?.[key];
          if (v === null || v === undefined) return null;
          const isDiscount = v < 0;
          return (
            <span key={key} className={isDiscount ? "text-positive" : "text-negative"}>
              {key.toUpperCase()} {v > 0 ? "+" : ""}
              {v.toFixed(1)}%
            </span>
          );
        })}
      </div>

      <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
        <p className="text-xs font-medium text-gray-500">{t("peerComparison.interpretationTitle")}</p>
        {(["per", "pbr", "ev_ebitda"] as const).map((key) => {
          const v = data.discount_premium?.[key];
          if (v === null || v === undefined) return null;
          const { judgmentLabel, explanation, tone } = buildInterpretation(key, v, t);
          return (
            <div key={key} className="text-xs">
              <span
                className={
                  tone === "cheaper" ? "text-positive" : tone === "richer" ? "text-negative" : "text-gray-400"
                }
              >
                {t(METRIC_LABEL_KEY[key])} {v > 0 ? "+" : ""}
                {v.toFixed(1)}% ({judgmentLabel})
              </span>
              {explanation && <p className="mt-0.5 text-gray-500">{explanation}</p>}
            </div>
          );
        })}
        {(() => {
          const selfRow = data.rows.find((r) => r.ticker === data.ticker);
          const medianRow = data.rows.find((r) => r.label === "업종 Median");
          if (!selfRow || !medianRow || selfRow.roe === null || medianRow.roe === null) return null;
          const diff = selfRow.roe - medianRow.roe;
          const SIMILAR_THRESHOLD = 2; // %p
          if (Math.abs(diff) < SIMILAR_THRESHOLD) {
            return (
              <div className="text-xs">
                <span className="text-gray-400">
                  {t("profitability.roe")} ({t("peerComparison.similarToPeers")})
                </span>
              </div>
            );
          }
          const isHigher = diff > 0;
          return (
            <div className="text-xs">
              <span className={isHigher ? "text-positive" : "text-negative"}>
                {t("profitability.roe")} {isHigher ? "+" : ""}
                {diff.toFixed(1)}%p ({isHigher ? t("peerComparison.higherThanPeers") : t("peerComparison.lowerThanPeers")})
              </span>
              <p className="mt-0.5 text-gray-500">{t(`glossary.roe${isHigher ? "High" : "Low"}`, "")}</p>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
