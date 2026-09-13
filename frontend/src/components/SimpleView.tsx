"use client";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import type { SimpleViewResponse } from "@/types/api";

/** data가 아직 없을 때(로딩 중)도 항목 틀을 그대로 보여주기 위한 라벨 순서. */
const ROW_LABEL_KEYS = [
  "simpleView.priceLevel",
  "simpleView.growth",
  "simpleView.profitability",
  "simpleView.financialHealth",
  "simpleView.newsSentiment",
  "simpleView.historicalSimilarity",
  "simpleView.aiOutlook",
] as const;

/**
 * Simple View (요구사항 23): 전문 금융용어를 최소화한 요약 화면.
 * data가 null(로딩 중)이어도 카드 틀은 즉시 렌더링하고 "불러오는 중" 상태를 표시한다.
 */
export function SimpleView({ data }: { data: SimpleViewResponse | null }) {
  const { t } = useTranslation();

  const rows: { labelKey: string; level: { label: string; detail: string } | null }[] = data
    ? [
        { labelKey: "simpleView.priceLevel", level: data.price_level },
        { labelKey: "simpleView.growth", level: data.growth_level },
        { labelKey: "simpleView.profitability", level: data.profitability_level },
        { labelKey: "simpleView.financialHealth", level: data.financial_health_level },
        { labelKey: "simpleView.newsSentiment", level: data.news_sentiment_level },
        { labelKey: "simpleView.historicalSimilarity", level: data.historical_similarity_level },
        { labelKey: "simpleView.aiOutlook", level: data.ai_outlook },
      ]
    : ROW_LABEL_KEYS.map((labelKey) => ({ labelKey, level: null }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {rows.map((row) => (
          <details key={row.labelKey} className="rounded border border-gray-200 bg-white p-4">
            <summary className="flex cursor-pointer items-center justify-between font-medium text-gray-700">
              <span>{t(row.labelKey)}</span>
              <span className={row.level ? "text-brand" : "text-gray-400"}>
                {row.level ? row.level.label : t("common.loading")}
              </span>
            </summary>
            {row.level && <p className="mt-2 text-sm text-gray-500">{row.level.detail}</p>}
          </details>
        ))}
      </div>

      <div className="rounded border border-gray-200 bg-white p-4">
        <h3 className="mb-2 font-semibold text-brand">{t("simpleView.riskFactors")}</h3>
        {data ? (
          <ul className="list-inside list-disc space-y-1 text-sm text-gray-600">
            {data.risk_factors.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-gray-400">{t("common.loading")}</p>
        )}
      </div>
    </div>
  );
}
