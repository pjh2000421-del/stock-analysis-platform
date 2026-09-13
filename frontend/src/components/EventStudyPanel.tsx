"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { formatPercent } from "@/lib/format";
import { api } from "@/lib/api";
import type { EventStudyResponse } from "@/types/api";

/**
 * Event Study 패널 (요구사항 15, 43): 뉴스 카드를 펼치면 해당 이벤트 발생일(Day 0)을
 * 기준으로 -20 ~ +60 거래일 구간의 주가 반응(수익률 %)을 차트로 보여준다.
 *
 * 아직 이벤트 발생 직후라 데이터가 부족하거나(insufficient_data), 이 뉴스에서
 * Event 정보 자체를 추출하지 못한 경우(no_event)에는 그 이유를 그대로 안내한다
 * (요구사항 74: 계산할 수 없으면 "데이터 없음"을 명확히 표시하고 억지로 채우지 않는다).
 */
export function EventStudyPanel({ newsId }: { newsId: number }) {
  const { t, locale } = useTranslation();
  const [data, setData] = useState<EventStudyResponse | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    api
      .getEventStudy(newsId)
      .then((res) => !cancelled && setData(res))
      .catch(() => !cancelled && setData(null));
    return () => {
      cancelled = true;
    };
  }, [newsId]);

  if (data === undefined) {
    return <p className="mt-3 text-xs text-gray-400">{t("common.loading")}</p>;
  }

  if (!data || data.status !== "ok" || !data.summary) {
    const message =
      data?.message ??
      (data?.status === "insufficient_data"
        ? t("eventStudy.insufficientData")
        : t("eventStudy.noEvent"));
    return <p className="mt-3 rounded bg-gray-50 px-3 py-2 text-xs text-gray-500">{message}</p>;
  }

  const chartData = data.current_event.map((p) => ({ offset: p.offset_days, returnPct: p.return_pct }));
  const s = data.summary;

  return (
    <div className="mt-3 border-t border-gray-100 pt-3">
      <div style={{ width: "100%", height: 200 }}>
        <ResponsiveContainer>
          <LineChart data={chartData} margin={{ top: 5, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis
              dataKey="offset"
              tick={{ fontSize: 11 }}
              label={{ value: t("eventStudy.tradingDaysAxis"), position: "insideBottom", offset: -2, fontSize: 11 }}
            />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} width={44} />
            <Tooltip
              formatter={(value: number) => [formatPercent(value, locale, 1), t("eventStudy.returnLabel")]}
              labelFormatter={(label) => `D${label >= 0 ? "+" : ""}${label}`}
            />
            <ReferenceLine x={0} stroke="#999" strokeDasharray="4 2" />
            <ReferenceLine y={0} stroke="#ddd" />
            <Line type="monotone" dataKey="returnPct" stroke="#2563eb" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 sm:grid-cols-4">
        <span>D+1: {formatPercent(s.return_1d, locale, 1)}</span>
        <span>D+5: {formatPercent(s.return_5d, locale, 1)}</span>
        <span>D+20: {formatPercent(s.return_20d, locale, 1)}</span>
        <span>D+60: {formatPercent(s.return_60d, locale, 1)}</span>
      </div>
      {s.benchmark_index && (
        <p className="mt-1 text-[11px] text-gray-400">
          {t("eventStudy.excessReturnNote")} ({s.benchmark_index}): {t("eventStudy.excessReturn5d")}{" "}
          {formatPercent(s.excess_return_5d, locale, 1)}
        </p>
      )}
      <p className="mt-1 text-[11px] leading-snug text-gray-400">{t("eventStudy.disclaimer")}</p>
    </div>
  );
}
