"use client";

import { useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { formatKrwAmount, formatPercent } from "@/lib/format";
import { api } from "@/lib/api";
import { Tooltip } from "@/components/Tooltip";
import type { DCFAssumptions, DCFResult } from "@/types/api";

const DEFAULT_ASSUMPTIONS: DCFAssumptions = {
  revenue_growth_rate: 0.05,
  operating_margin: 0.15,
  tax_rate: 0.22,
  capex_pct_revenue: 0.05,
  working_capital_pct_revenue: 0.02,
  wacc: 0.09,
  terminal_growth_rate: 0.02,
  projection_years: 5,
};

type NumericField = Exclude<keyof DCFAssumptions, "projection_years">;

const FIELDS: { key: NumericField; labelKey: string }[] = [
  { key: "revenue_growth_rate", labelKey: "dcfPage.revenueGrowth" },
  { key: "operating_margin", labelKey: "dcfPage.operatingMargin" },
  { key: "tax_rate", labelKey: "dcfPage.taxRate" },
  { key: "capex_pct_revenue", labelKey: "dcfPage.capexPctRevenue" },
  { key: "working_capital_pct_revenue", labelKey: "dcfPage.workingCapitalPctRevenue" },
  { key: "wacc", labelKey: "dcfPage.wacc" },
  { key: "terminal_growth_rate", labelKey: "dcfPage.terminalGrowthRate" },
];

/** DCF Calculator (요구사항 22): 사용자가 직접 가정을 조정하여 기업가치를 추정한다. */
export function DCFCalculator({ ticker }: { ticker: string }) {
  const { t, locale } = useTranslation();
  const [assumptions, setAssumptions] = useState<DCFAssumptions>(DEFAULT_ASSUMPTIONS);
  const [result, setResult] = useState<DCFResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField(key: NumericField, value: number) {
    setAssumptions((prev) => ({ ...prev, [key]: value }));
  }

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.runDcf(ticker, assumptions);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="rounded border border-gray-200 bg-white p-4">
        <h3 className="mb-3 flex items-center font-semibold text-brand">
          {t("company.dcf")}
          <Tooltip text={t("glossary.dcf")} />
        </h3>
        <div className="space-y-3">
          {FIELDS.map((f) => (
            <div key={f.key} className="flex items-center justify-between gap-3">
              <label className="text-sm text-gray-500">{t(f.labelKey)}</label>
              <input
                type="number"
                step={0.01}
                value={assumptions[f.key]}
                onChange={(e) => updateField(f.key, Number(e.target.value))}
                className="w-24 rounded border border-gray-300 px-2 py-1 text-right text-sm tabular-num"
              />
            </div>
          ))}
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="mt-4 w-full rounded bg-brand py-2 text-sm font-medium text-white hover:bg-brand-light disabled:opacity-50"
        >
          {loading ? t("common.loading") : t("dcfPage.runDcf")}
        </button>
        {error && <p className="mt-2 text-sm text-negative">{error}</p>}
      </div>

      <div className="rounded border border-gray-200 bg-white p-4">
        <h3 className="mb-3 font-semibold text-brand">결과</h3>
        {!result && <p className="text-sm text-gray-400">{t("dcfPage.runDcf")}</p>}
        {result && (
          <div className="space-y-2 text-sm">
            <Row label={t("dcfPage.enterpriseValue")} value={formatKrwAmount(result.enterprise_value, locale)} />
            <Row label={t("dcfPage.equityValue")} value={formatKrwAmount(result.equity_value, locale)} />
            <Row
              label={t("dcfPage.pricePerShare")}
              value={
                result.estimated_price_per_share
                  ? formatKrwAmount(result.estimated_price_per_share, locale)
                  : t("common.notAvailable")
              }
            />
            <Row
              label={t("dcfPage.currentPrice")}
              value={result.current_price ? formatKrwAmount(result.current_price, locale) : t("common.notAvailable")}
            />
            <Row
              label={t("dcfPage.upside")}
              value={result.upside_pct !== null ? formatPercent(result.upside_pct, locale) : t("common.notAvailable")}
            />
            <p className="mt-3 text-xs text-gray-400">{result.note}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-gray-100 py-1.5 last:border-0">
      <span className="text-gray-500">{label}</span>
      <span className="tabular-num font-medium">{value}</span>
    </div>
  );
}
