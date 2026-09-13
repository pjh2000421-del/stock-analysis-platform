"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { CompanySearchResult } from "@/types/api";

/** 페이지 상단 상시 노출되는 기업 검색창 (요구사항 4). */
export function SearchBar() {
  const { t } = useTranslation();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CompanySearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleChange(value: string) {
    setQuery(value);
    if (!value.trim()) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    setIsOpen(true);
    try {
      const res = await api.searchCompanies(value);
      setResults(res.results);
    } catch (e) {
      setResults([]);
      setErrorMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setIsLoading(false);
    }
  }

  function goToCompany(ticker: string) {
    setIsOpen(false);
    setQuery("");
    router.push(`/company/${ticker}`);
  }

  /** 검색 버튼 클릭 또는 Enter 입력 시: 검색 결과 페이지로 전환 (요구사항 4). */
  function goToSearchPage() {
    const trimmed = query.trim();
    if (!trimmed) return;
    setIsOpen(false);
    router.push(`/search?q=${encodeURIComponent(trimmed)}`);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      goToSearchPage();
    }
  }

  return (
    <div className="relative w-full max-w-xl">
      <div className="flex items-stretch gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("common.searchPlaceholder")}
          className="w-full rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-brand focus:outline-none"
          onFocus={() => results.length > 0 && setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 150)}
        />
        <button
          type="button"
          onClick={goToSearchPage}
          className="shrink-0 rounded bg-white px-3 py-2 text-sm font-medium text-brand hover:bg-surface"
        >
          {t("common.searchButton")}
        </button>
      </div>
      {isOpen && (
        <ul className="absolute z-10 mt-1 w-full rounded border border-gray-200 bg-white shadow-lg">
          {isLoading && <li className="px-3 py-2 text-sm text-gray-400">{t("common.loading")}</li>}
          {!isLoading && errorMessage && (
            <li className="px-3 py-2 text-sm text-negative">{errorMessage}</li>
          )}
          {!isLoading && !errorMessage && results.length === 0 && (
            <li className="px-3 py-2 text-sm text-gray-400">{t("common.noData")}</li>
          )}
          {results.map((r) => (
            <li key={r.ticker}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-gray-900 hover:bg-surface"
                onMouseDown={() => goToCompany(r.ticker)}
              >
                <span>
                  <span className="font-medium text-gray-900">{r.company_name}</span>{" "}
                  <span className="text-gray-400">{r.ticker}</span>
                </span>
                <span className="text-xs text-gray-400">
                  {/* 투자용 업종(investment_industry)을 우선 표시하고, 아직 분류가
                      확보되지 않은 기업만 KRX 원본 업종(industry)으로 보조 표시한다. */}
                  {r.market} {r.investment_industry ? `· ${r.investment_industry}` : r.industry ? `· ${r.industry}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
