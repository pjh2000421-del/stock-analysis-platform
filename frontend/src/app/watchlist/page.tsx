"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { WatchlistItemOut } from "@/types/api";

/** Watchlist 페이지 (요구사항 46). */
export default function WatchlistPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<WatchlistItemOut[]>([]);
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    api
      .getWatchlist()
      .then(setItems)
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function remove(ticker: string) {
    await api.removeWatchlist(ticker);
    refresh();
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-brand">{t("watchlistPage.title")}</h1>
      {loading && <p className="text-sm text-gray-400">{t("common.loading")}</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-gray-400">{t("watchlistPage.empty")}</p>
      )}
      <ul className="divide-y divide-gray-100 rounded border border-gray-200 bg-white">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <Link href={`/company/${item.ticker}`} className="font-medium hover:text-brand">
                {item.company_name}
              </Link>
              <span className="ml-2 text-xs text-gray-400">{item.ticker}</span>
              {item.latest_important_news_title && (
                <p className="mt-1 text-xs text-gray-400">{item.latest_important_news_title}</p>
              )}
            </div>
            <button
              onClick={() => remove(item.ticker)}
              className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-500 hover:border-negative hover:text-negative"
            >
              {t("watchlistPage.remove")}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
