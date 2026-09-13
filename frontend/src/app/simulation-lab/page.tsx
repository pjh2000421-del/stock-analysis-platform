"use client";

import { useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { MarketSimulationResult } from "@/types/api";

const PERSONAS = ["Value", "Momentum", "Long-term", "Risk Averse", "News-driven", "SNS-driven"];

/** Market Simulation Lab (요구사항 50~52) - Phase6 Mock Adapter 기반 UI. */
export default function SimulationLabPage() {
  const { t } = useTranslation();
  const [newsId, setNewsId] = useState(1);
  const [weights, setWeights] = useState<Record<string, number>>({
    Value: 30,
    Momentum: 20,
    "Long-term": 10,
    "Risk Averse": 20,
    "News-driven": 10,
    "SNS-driven": 10,
  });
  const [result, setResult] = useState<MarketSimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const total = Object.values(weights).reduce((a, b) => a + b, 0);

  async function run() {
    setError(null);
    try {
      const res = await api.runSimulation({
        news_id: newsId,
        personas: PERSONAS.map((name) => ({ name, risk_tolerance: 0.5, investment_horizon: 0.5, news_dependency: 0.5, social_dependency: 0.5, trend_dependency: 0.5, fundamental_dependency: 0.5 })),
        persona_mix: { persona_weights: Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, v / 100])) },
        steps: 60,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-brand">{t("simulationLabPage.title")}</h1>
      <p className="text-sm text-gray-500">{t("simulationLabPage.description")}</p>

      <div className="rounded border border-gray-200 bg-white p-4">
        <label className="mb-1 block text-sm text-gray-500">뉴스 ID</label>
        <input
          type="number"
          value={newsId}
          onChange={(e) => setNewsId(Number(e.target.value))}
          className="mb-4 w-32 rounded border border-gray-300 px-3 py-2 text-sm"
        />

        <div className="space-y-2">
          {PERSONAS.map((p) => (
            <div key={p} className="flex items-center gap-3">
              <span className="w-32 text-sm text-gray-600">{p}</span>
              <input
                type="range"
                min={0}
                max={100}
                value={weights[p]}
                onChange={(e) => setWeights((prev) => ({ ...prev, [p]: Number(e.target.value) }))}
                className="flex-1"
              />
              <span className="w-10 text-right text-sm tabular-num">{weights[p]}%</span>
            </div>
          ))}
        </div>
        <p className={`mt-2 text-xs ${total === 100 ? "text-gray-400" : "text-negative"}`}>합계: {total}%</p>

        <button
          onClick={run}
          className="mt-4 rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-light"
        >
          {t("simulationLabPage.run")}
        </button>
        {error && <p className="mt-2 text-sm text-negative">{error}</p>}
      </div>

      {result && (
        <div className="rounded border border-gray-200 bg-white p-4 text-sm">
          <p className="mb-2 text-xs text-yellow-600">MOCK RESULT — {result.note}</p>
          <p>Bubble Indicator: {result.bubble_indicator}</p>
          <p>Herding Indicator: {result.herding_indicator}</p>
          <p className="mt-2 text-gray-400">
            가격 경로(최초 10 step): {result.price_path.slice(0, 10).join(", ")}
          </p>
        </div>
      )}
    </div>
  );
}
