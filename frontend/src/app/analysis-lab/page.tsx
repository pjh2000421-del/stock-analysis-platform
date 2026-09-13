"use client";

import { useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";

const TARGETS = ["next_day_return", "return_5d", "return_20d", "up_down", "volatility", "residual", "excess_return"];
const FEATURE_GROUPS = [
  "price",
  "volume",
  "news_sentiment",
  "news_frequency",
  "event_type",
  "historical_similarity",
  "valuation",
  "fundamental",
  "market_index",
  "fx_rate",
  "interest_rate",
  "volatility",
];
const MODELS = ["linear_regression", "logistic_regression", "random_forest", "xgboost", "ann", "lstm", "auto_compare"];

interface ModelMetrics {
  directional_accuracy: number | null;
  mae: number | null;
  rmse: number | null;
  r2: number | null;
  accuracy: number | null;
  precision: number | null;
  recall: number | null;
  f1: number | null;
  roc_auc: number | null;
}

interface AnalysisResultOut {
  model: string;
  target: string;
  prediction: { value?: number; direction?: string; probability_up?: number };
  metrics: ModelMetrics | null;
  feature_importance: Record<string, number> | null;
  confidence: string | null;
  prediction_interval: { lower: number; upper: number } | null;
}

interface AnalysisJobResult {
  job_id: number;
  status: string;
  results: AnalysisResultOut[];
  error_message: string | null;
}

function formatNumber(n: number | null | undefined, digits = 4) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toFixed(digits);
}

/**
 * Analysis Lab (요구사항 40, 41).
 * 사용자가 직접 Feature/Lag/Model을 조합해 분석을 요청할 수 있는 UI.
 * Phase3 MVP: price/volume/news_sentiment/news_frequency/event_type Feature +
 * 선형/로지스틱회귀/랜덤포레스트/XGBoost(회귀만)/Auto Compare 모델을 실제로 학습해
 * 백테스트 성능과 "지금 시점" 예측을 보여준다. 그 외 Feature(historical_similarity 등)나
 * 예측 대상(excess_return 등)은 아직 지원하지 않아 결과의 error_message에 안내된다.
 */
export default function AnalysisLabPage() {
  const { t } = useTranslation();
  const [ticker, setTicker] = useState("");
  const [target, setTarget] = useState(TARGETS[1]);
  const [model, setModel] = useState(MODELS[2]);
  const [features, setFeatures] = useState<string[]>(["price"]);
  const [lag, setLag] = useState(0);
  const [jobResult, setJobResult] = useState<AnalysisJobResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleFeature(f: string) {
    setFeatures((prev) => (prev.includes(f) ? prev.filter((x) => x !== f) : [...prev, f]));
  }

  async function run() {
    setError(null);
    setJobResult(null);
    setLoading(true);
    try {
      const today = new Date();
      const oneYearAgo = new Date(today);
      oneYearAgo.setFullYear(today.getFullYear() - 1);

      const created = (await api.runAnalysis({
        ticker,
        start_date: oneYearAgo.toISOString().slice(0, 10),
        end_date: today.toISOString().slice(0, 10),
        features,
        lags: [lag],
        target,
        model,
        scaler: "minmax",
        validation_method: "time_series_split",
        hyperparameters: {},
      })) as { job_id: number; status: string };

      // 지금은 Job이 요청 안에서 동기적으로 끝까지 실행되므로(별도 백그라운드 큐 없음),
      // 생성 직후 바로 결과를 조회하면 최종 상태(done/failed)를 받을 수 있다.
      const full = (await api.getAnalysisResult(created.job_id)) as AnalysisJobResult;
      setJobResult(full);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-brand">{t("analysisLabPage.title")}</h1>
      <p className="text-sm text-gray-500">{t("analysisLabPage.description")}</p>

      <div className="grid grid-cols-1 gap-4 rounded border border-gray-200 bg-white p-4 lg:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm text-gray-500">{t("common.search")}</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="005930"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm text-gray-500">{t("analysisLabPage.target")}</label>
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            {TARGETS.map((tOpt) => (
              <option key={tOpt} value={tOpt}>
                {tOpt}
              </option>
            ))}
          </select>
        </div>

        <div className="lg:col-span-2">
          <label className="mb-1 block text-sm text-gray-500">{t("analysisLabPage.features")}</label>
          <div className="flex flex-wrap gap-2">
            {FEATURE_GROUPS.map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => toggleFeature(f)}
                className={`rounded px-2 py-1 text-xs ${
                  features.includes(f) ? "bg-brand text-white" : "bg-surface text-gray-500"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm text-gray-500">{t("analysisLabPage.lags")}</label>
          <select
            value={lag}
            onChange={(e) => setLag(Number(e.target.value))}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            {[0, 1, 2, 3, 5, 10].map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm text-gray-500">{t("analysisLabPage.model")}</label>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
      </div>

      <button
        onClick={run}
        disabled={!ticker || loading}
        className="rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-light disabled:opacity-50"
      >
        {loading ? "..." : t("analysisLabPage.run")}
      </button>

      {error && <p className="text-sm text-negative">{error}</p>}

      {jobResult && (
        <div className="space-y-3 rounded border border-gray-200 bg-white p-4">
          <p className="text-sm text-gray-500">
            Job #{jobResult.job_id} - {jobResult.status}
          </p>

          {jobResult.error_message && (
            <p className="text-sm text-gray-500">참고: {jobResult.error_message}</p>
          )}

          {jobResult.results.length === 0 && jobResult.status === "failed" && (
            <p className="text-sm text-negative">분석에 실패했습니다. 위 참고 메시지를 확인해주세요.</p>
          )}

          {jobResult.results.map((r) => {
            const topFeatures = r.feature_importance
              ? Object.entries(r.feature_importance)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 5)
              : null;
            const predictionText =
              r.prediction.value !== undefined
                ? `예측값: ${formatNumber(r.prediction.value)}`
                : `방향: ${r.prediction.direction}${
                    r.prediction.probability_up !== undefined
                      ? ` (상승 확률 ${formatNumber(r.prediction.probability_up, 2)})`
                      : ""
                  }`;

            return (
              <div key={r.model} className="rounded border border-gray-100 bg-surface p-3">
                <p className="text-sm font-medium text-gray-700">
                  {r.model} · 신뢰도 {r.confidence ?? "-"}
                </p>
                <p className="mt-1 text-sm text-gray-600">{predictionText}</p>
                {r.prediction_interval && (
                  <p className="text-xs text-gray-500">
                    예측 구간: {formatNumber(r.prediction_interval.lower)} ~{" "}
                    {formatNumber(r.prediction_interval.upper)}
                  </p>
                )}
                {r.metrics &&
                  (() => {
                    const m = r.metrics;
                    const parts = [
                      m.mae !== null && `MAE ${formatNumber(m.mae)}`,
                      m.rmse !== null && `RMSE ${formatNumber(m.rmse)}`,
                      m.r2 !== null && `R² ${formatNumber(m.r2)}`,
                      m.directional_accuracy !== null && `방향 적중률 ${formatNumber(m.directional_accuracy, 2)}`,
                      m.accuracy !== null && `정확도 ${formatNumber(m.accuracy, 2)}`,
                      m.precision !== null && `정밀도 ${formatNumber(m.precision, 2)}`,
                      m.recall !== null && `재현율 ${formatNumber(m.recall, 2)}`,
                      m.f1 !== null && `F1 ${formatNumber(m.f1, 2)}`,
                      m.roc_auc !== null && `ROC-AUC ${formatNumber(m.roc_auc, 2)}`,
                    ].filter(Boolean);
                    return parts.length > 0 ? (
                      <p className="mt-1 text-xs text-gray-500">{parts.join(" · ")}</p>
                    ) : null;
                  })()}
                {topFeatures && (
                  <p className="mt-1 text-xs text-gray-400">
                    주요 Feature: {topFeatures.map(([name, v]) => `${name}(${formatNumber(v, 2)})`).join(", ")}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
