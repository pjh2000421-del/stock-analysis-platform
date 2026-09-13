"use client";

import { useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { formatDate } from "@/lib/format";
import { EventStudyPanel } from "@/components/EventStudyPanel";
import type { NewsItem } from "@/types/api";

function sentimentLabel(score: number | null, t: (k: string, f?: string) => string) {
  if (score === null) return null;
  if (score > 0.15) return { text: t("news.sentimentPositive"), cls: "text-positive" };
  if (score < -0.15) return { text: t("news.sentimentNegative"), cls: "text-negative" };
  return { text: t("news.sentimentNeutral"), cls: "text-gray-500" };
}

function NewsCard({ n }: { n: NewsItem }) {
  const { t, locale } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const sentiment = sentimentLabel(n.sentiment_score, t);

  return (
    <div className="rounded border border-gray-200 bg-white p-4 hover:border-brand">
      <a href={n.url} target="_blank" rel="noreferrer" className="block">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>
            {n.source ?? "-"} · {n.published_at ? formatDate(n.published_at, locale) : "-"}
          </span>
          {n.event_type && (
            <span className="rounded bg-surface px-2 py-0.5 text-gray-600">{n.event_type}</span>
          )}
        </div>
        <h3 className="mt-1 font-medium text-gray-900">{n.title}</h3>
        {n.summary && <p className="mt-1 line-clamp-2 text-sm text-gray-500">{n.summary}</p>}
        <div className="mt-2 flex flex-wrap gap-3 text-xs">
          {sentiment && <span className={sentiment.cls}>{sentiment.text}</span>}
          {n.importance_score !== null && (
            <span className="text-gray-400">중요도 {Math.round(n.importance_score)}</span>
          )}
          {n.related_count > 0 && (
            <span className="text-gray-400">
              {t("news.relatedCoverage")} {n.related_count}
            </span>
          )}
          {n.is_mock && <span className="text-yellow-600">MOCK</span>}
        </div>
      </a>

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-2 text-xs font-medium text-brand hover:underline"
      >
        {expanded ? t("eventStudy.hide") : t("eventStudy.show")}
      </button>

      {expanded && <EventStudyPanel newsId={n.id} />}
    </div>
  );
}

/** 뉴스 카드 목록 (요구사항 8). */
export function NewsList({
  news,
  providerStatus,
}: {
  news: NewsItem[];
  providerStatus?: Record<string, string>;
}) {
  const { t } = useTranslation();
  const unavailable = Object.entries(providerStatus ?? {}).filter(([, v]) => v === "unavailable");

  return (
    <div className="space-y-3">
      {unavailable.length > 0 && (
        <p className="rounded bg-yellow-50 px-3 py-2 text-xs text-yellow-700">
          {t("news.providerUnavailable")}: {unavailable.map(([k]) => k).join(", ")}
        </p>
      )}
      {news.length === 0 && <p className="text-sm text-gray-400">{t("common.noData")}</p>}
      {news.map((n) => (
        <NewsCard key={n.id} n={n} />
      ))}
    </div>
  );
}
