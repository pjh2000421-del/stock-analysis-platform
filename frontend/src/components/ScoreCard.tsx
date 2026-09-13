"use client";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import type { CompositeScoreResponse } from "@/types/api";

/** 데이터가 아직 없을 때(로딩 중) 표시할 자리표시자 카테고리 (요구사항 25의 4개 카테고리와 동일). */
const PLACEHOLDER_CATEGORIES = ["VALUATION", "GROWTH", "PROFITABILITY", "FINANCIAL_HEALTH"];

interface DisplayCategory {
  category: string;
  score: number | null;
  weight: number;
  is_na: boolean;
}

/**
 * 종합 기업 분석 점수 (요구사항 25). black-box 방지를 위해 weight/구성요소를 함께 노출한다.
 * score가 아직 로딩 중(null)이어도 카드/표 틀은 즉시 렌더링하고 내부에 로딩 상태를 표시한다.
 */
export function ScoreCard({ score }: { score: CompositeScoreResponse | null }) {
  const { t } = useTranslation();
  const categories: DisplayCategory[] = score
    ? score.scores.map((s) => ({ category: s.category, score: s.score, weight: s.weight, is_na: s.is_na }))
    : PLACEHOLDER_CATEGORIES.map((category) => ({ category, score: null, weight: 0, is_na: false }));

  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-brand">종합 점수</h3>
        <span className="text-xs text-gray-400">{score ? `weights v${score.weights_config_version}` : " "}</span>
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {categories.map((s) => (
          <div key={s.category} className="rounded bg-surface p-3 text-center">
            <div className="text-xs uppercase text-gray-400">{s.category}</div>
            <div className={`mt-1 text-xl font-bold tabular-num ${!score ? "text-gray-300" : ""}`}>
              {!score ? "..." : s.is_na ? "N/A" : `${s.score} / 100`}
            </div>
            <div className="mt-1 text-[10px] text-gray-400">
              {score ? `weight ${(s.weight * 100).toFixed(0)}%` : " "}
            </div>
          </div>
        ))}
      </div>
      {!score && <p className="mt-3 text-sm text-gray-400">{t("common.loading")}</p>}
      {score && score.total_score !== null && (
        <p className="mt-3 text-sm text-gray-500">
          종합 점수: <span className="font-semibold">{score.total_score} / 100</span>
        </p>
      )}
    </div>
  );
}
