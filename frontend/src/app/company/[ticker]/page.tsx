"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api, ApiError } from "@/lib/api";
import { CompanyHeader } from "@/components/CompanyHeader";
import { PriceChart } from "@/components/PriceChart";
import { NewsList } from "@/components/NewsList";
import { SimpleView } from "@/components/SimpleView";
import { ProView } from "@/components/ProView";
import { DCFCalculator } from "@/components/DCFCalculator";
import { AIQAPanel } from "@/components/AIQAPanel";
import type { CompanyDetail, NewsListResponse } from "@/types/api";

type Tab = "simple" | "pro" | "news" | "dcf";

/**
 * 기업 상세 페이지 (요구사항 6, 요구사항 65: Progressive Loading).
 * 기본정보/가격/차트를 먼저 로드하고, 뉴스/재무/고급분석은 탭 전환 시점에 로드한다.
 */
export default function CompanyDetailPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = params.ticker;
  const { t } = useTranslation();

  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<Tab>("simple");
  const [news, setNews] = useState<NewsListResponse | null>(null);
  const [inWatchlist, setInWatchlist] = useState(false);

  useEffect(() => {
    api
      .getCompanyDetail(ticker)
      .then(setCompany)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setNotFound(true);
      });
  }, [ticker]);

  useEffect(() => {
    if (!company) return;
    try {
      const raw = localStorage.getItem("recently_viewed_companies");
      const list: { ticker: string; company_name: string }[] = raw ? JSON.parse(raw) : [];
      const next = [
        { ticker: company.ticker, company_name: company.company_name },
        ...list.filter((c) => c.ticker !== company.ticker),
      ].slice(0, 8);
      localStorage.setItem("recently_viewed_companies", JSON.stringify(next));
    } catch {
      // localStorage 접근 불가 환경(프라이빗 모드 등) 대비
    }
  }, [company]);

  useEffect(() => {
    if (tab === "news" && !news) {
      api.getCompanyNews(ticker).then(setNews).catch(() => setNews(null));
    }
  }, [tab, news, ticker]);

  if (notFound) {
    return <p className="text-sm text-gray-500">{t("common.noData")}</p>;
  }
  if (!company) {
    return <p className="text-sm text-gray-400">{t("common.loading")}</p>;
  }

  async function toggleWatchlist() {
    if (inWatchlist) {
      await api.removeWatchlist(ticker);
      setInWatchlist(false);
    } else {
      await api.addWatchlist(ticker);
      setInWatchlist(true);
    }
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "simple", label: t("company.simpleView") },
    { key: "pro", label: t("company.proView") },
    { key: "news", label: t("company.news") },
    { key: "dcf", label: t("company.dcf") },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <CompanyHeader company={company} />
          </div>
          <button
            onClick={toggleWatchlist}
            className="mt-1 rounded border border-brand px-3 py-1.5 text-sm text-brand hover:bg-brand hover:text-white"
          >
            {inWatchlist ? t("watchlistPage.remove") : t("watchlistPage.add")}
          </button>
        </div>

        <PriceChart ticker={ticker} />

        <div className="flex gap-2 border-b border-gray-200">
          {tabs.map((tabItem) => (
            <button
              key={tabItem.key}
              onClick={() => setTab(tabItem.key)}
              className={`px-3 py-2 text-sm ${
                tab === tabItem.key
                  ? "border-b-2 border-brand font-semibold text-brand"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tabItem.label}
            </button>
          ))}
        </div>

        {tab === "simple" && <SimpleViewSection ticker={ticker} />}
        {tab === "pro" && <ProView ticker={ticker} company={company} />}
        {tab === "news" && (
          <NewsList news={news?.news ?? []} providerStatus={news?.provider_status} />
        )}
        {tab === "dcf" && <DCFCalculator ticker={ticker} />}
      </div>

      <div className="lg:sticky lg:top-4 lg:self-start">
        <AIQAPanel ticker={ticker} />
      </div>
    </div>
  );
}

function SimpleViewSection({ ticker }: { ticker: string }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.getCompanySimpleView>> | null>(null);

  useEffect(() => {
    setData(null);
    api.getCompanySimpleView(ticker).then(setData).catch(() => setData(null));
  }, [ticker]);

  // data가 아직 없어도(로딩 중) 항목 틀은 SimpleView 내부에서 즉시 렌더링한다.
  return <SimpleView data={data} />;
}
