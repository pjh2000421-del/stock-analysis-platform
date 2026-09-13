"use client";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { formatKrwAmount, formatKrwLargeAmount, formatNumber, formatPercent } from "@/lib/format";
import type { CompanyDetail } from "@/types/api";

/** 기업 상세 상단 요약 (요구사항 6). */
export function CompanyHeader({ company }: { company: CompanyDetail }) {
  const { t, locale } = useTranslation();
  const isUp = (company.price_change ?? 0) >= 0;

  // 화면에 기본으로 노출할 "업종"은 투자분석용 분류(classification.industry, 예: WICS
  // "반도체와반도체장비")를 최우선으로 쓴다. 아직 분류가 확보되지 않은 경우에만
  // "N/A"류 안내 문구를 보여주고, KRX 원본(KSIC) 업종을 대신 표시하지 않는다
  // (요구사항: 없는 데이터를 실제 분류인 것처럼 보여주지 않는다).
  const investmentIndustry = company.classification?.industry;
  const industryLabel = investmentIndustry ?? t("company.classificationPending");

  return (
    <div className="border-b border-gray-200 bg-white px-6 py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand">{company.company_name}</h1>
          <p className="mt-1 text-sm text-gray-400">
            {/* company.sector는 업종이 아니라 시장 소속부(우량기업부 등)라서 표시하지 않는다. */}
            {company.ticker} · {company.market ?? "-"} · {industryLabel}
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-semibold tabular-num">
            {formatKrwAmount(company.current_price, locale)}
          </div>
          <div
            className={`tabular-num text-sm font-medium ${
              isUp ? "text-positive" : "text-negative"
            }`}
          >
            {company.price_change !== null ? (isUp ? "+" : "") : ""}
            {formatNumber(company.price_change, locale, 0)} (
            {formatPercent(company.price_change_pct, locale)})
          </div>
        </div>
      </div>
      <div className="mt-4 flex gap-8 text-sm text-gray-500">
        <div>
          <span className="text-gray-400">{t("company.marketCap")}: </span>
          {company.market_cap
            ? formatKrwLargeAmount(company.market_cap, locale)
            : t("common.notAvailable")}
        </div>
      </div>
    </div>
  );
}
