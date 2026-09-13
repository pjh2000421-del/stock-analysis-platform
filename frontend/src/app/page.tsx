"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { WatchlistItemOut } from "@/types/api";

/**
 * Dashboard (요구사항 57): 기업 검색 / Watchlist / 최근 중요 뉴스 / 최근 분석한 기업 / 시장 요약
 * 과도하게 많은 정보를 넣지 않고 핵심 위젯 위주로 구성한다.
 */
export default function DashboardPage() {
  const { t } = useTranslation();
  const [watchlist, setWatchlist] = useState<WatchlistItemOut[]>([]);
  const [recentlyViewed, setRecentlyViewed] = useState<{ ticker: string; company_name: string }[]>(
    []
  );

  useEffect(() => {
    api.getWatchlist().then(setWatchlist).catch(() => setWatchlist([]));
    try {
      const raw = localStorage.getItem("recently_viewed_companies");
      if (raw) setRecentlyViewed(JSON.parse(raw));
    } catch {
      // localStorage 접근 불가 환경(프라이빗 모드 등) 대비
    }
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-brand">{t("dashboard.title")}</h1>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded border border-gray-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-gray-700">{t("dashboard.myWatchlist")}</h2>
          {watchlist.length === 0 ? (
            <p className="text-sm text-gray-400">{t("watchlistPage.empty")}</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {watchlist.map((w) => (
                <li key={w.id} className="flex items-center justify-between py-2 text-sm">
                  <Link href={`/company/${w.ticker}`} className="font-medium hover:text-brand">
                    {w.company_name}
                  </Link>
                  <span className="text-gray-400">{w.ticker}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded border border-gray-200 bg-white p-4">
          <h2 className="mb-3 font-semibold text-gray-700">{t("dashboard.recentlyAnalyzed")}</h2>
          {recentlyViewed.length === 0 ? (
            <p className="text-sm text-gray-400">{t("common.noData")}</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {recentlyViewed.map((c) => (
                <li key={c.ticker}>
                  <Link
                    href={`/company/${c.ticker}`}
                    className="rounded bg-surface px-2 py-1 text-xs text-gray-600 hover:bg-gray-200"
                  >
                    {c.company_name}({c.ticker})
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded border border-gray-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 font-semibold text-gray-700">{t("dashboard.recentImportantNews")}</h2>
          <p className="text-sm text-gray-400">{t("common.comingSoon")}</p>
        </section>

        <section className="rounded border border-gray-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 font-semibold text-gray-700">{t("dashboard.marketSummary")}</h2>
          <p className="text-sm text-gray-400">{t("common.comingSoon")}</p>
        </section>
      </div>
    </div>
  );
}
