"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { CompanySearchResult } from "@/types/api";

/**
 * 검색 결과 페이지 (요구사항 4).
 * 상단 검색창에서 Enter 또는 검색 버튼을 눌렀을 때 이동하는 전체 목록 페이지.
 */
function SearchResults() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const query = searchParams.get("q") ?? "";

  const [results, setResults] = useState<CompanySearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    api
      .searchCompanies(query)
      .then((res) => setResults(res.results))
      .catch((e) => {
        setResults([]);
        setErrorMessage(e instanceof Error ? e.message : String(e));
      })
      .finally(() => setIsLoading(false));
  }, [query]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-brand">
        {t("searchPage.title")} {query && <span className="text-gray-500">&ldquo;{query}&rdquo;</span>}
      </h1>

      {isLoading && <p className="text-sm text-gray-400">{t("common.loading")}</p>}
      {!isLoading && errorMessage && <p className="text-sm text-negative">{errorMessage}</p>}
      {!isLoading && !errorMessage && results.length === 0 && (
        <p className="text-sm text-gray-400">{t("searchPage.noResults")}</p>
      )}

      {!isLoading && !errorMessage && results.length > 0 && (
        <ul className="divide-y divide-gray-100 rounded border border-gray-200 bg-white">
          {results.map((r) => (
            <li key={r.ticker}>
              <Link
                href={`/company/${r.ticker}`}
                className="flex items-center justify-between px-4 py-3 text-sm hover:bg-surface"
              >
                <span>
                  <span className="font-medium text-gray-900">{r.company_name}</span>{" "}
                  <span className="text-gray-400">{r.ticker}</span>
                </span>
                <span className="text-xs text-gray-400">
                  {r.market} {r.investment_industry ? `· ${r.investment_industry}` : r.industry ? `· ${r.industry}` : ""}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchResults />
    </Suspense>
  );
}
