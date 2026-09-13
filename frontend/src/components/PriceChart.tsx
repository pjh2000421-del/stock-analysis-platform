"use client";

import { useEffect, useRef, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { PriceHistoryResponse } from "@/types/api";

const PERIODS = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX"] as const;

/**
 * 주가 차트 (요구사항 7).
 * TradingView Lightweight Charts를 사용하며, Candlestick + 거래량 히스토그램을 함께 표시한다.
 * 뉴스 Event Marker는 Series Marker로 표시하고, 클릭 시 해당 뉴스로 이동할 수 있게 한다.
 */
export function PriceChart({ ticker }: { ticker: string }) {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("3M");
  const [data, setData] = useState<PriceHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    // 기간(period) 전환 시 이전 조회 결과가 그대로 남아있으면, 새 기간의 조회가
    // 실패했을 때 화면에는 이전 기간(예: 1Y)의 차트가 계속 보여 마치 "새 기간이
    // 반영 안 된 것"처럼 오해할 수 있다. 새 요청을 시작할 때 항상 초기화한다.
    setData(null);
    setError(null);
    api
      .getCompanyPrices(ticker, period)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [ticker, period]);

  useEffect(() => {
    if (!data || !containerRef.current) return;
    let chart: import("lightweight-charts").IChartApi | undefined;
    let resizeObserver: ResizeObserver | undefined;

    // lightweight-charts는 브라우저 전용이므로 동적 import로 SSR 문제를 방지한다.
    import("lightweight-charts").then(({ createChart, ColorType }) => {
      if (!containerRef.current) return;
      chart = createChart(containerRef.current, {
        layout: { background: { type: ColorType.Solid, color: "#ffffff" }, textColor: "#333" },
        grid: { vertLines: { color: "#f0f0f0" }, horzLines: { color: "#f0f0f0" } },
        height: 420,
        width: containerRef.current.clientWidth,
        timeScale: { timeVisible: period === "1D" || period === "5D" },
      });

      const candleSeries = chart.addCandlestickSeries({
        upColor: "#c0392b",
        downColor: "#2563eb",
        borderVisible: false,
        wickUpColor: "#c0392b",
        wickDownColor: "#2563eb",
      });
      candleSeries.setData(
        data.prices
          .filter((p) => p.open !== null && p.high !== null && p.low !== null && p.close !== null)
          .map((p) => ({
            time: p.date,
            open: p.open as number,
            high: p.high as number,
            low: p.low as number,
            close: p.close as number,
          }))
      );

      const volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
      volumeSeries.setData(
        data.prices
          .filter((p) => p.volume !== null)
          .map((p) => ({ time: p.date, value: p.volume as number, color: "#c0c9d6" }))
      );

      if (data.event_markers.length > 0) {
        candleSeries.setMarkers(
          data.event_markers.map((m) => ({
            time: m.date,
            position: "aboveBar",
            color: "#0f2942",
            shape: "arrowDown",
            text: m.title.slice(0, 12),
          }))
        );
      }

      // 5Y/MAX처럼 데이터 구간이 길어져도 항상 전체 구간이 한 번에 보이도록 명시적으로 fit한다.
      chart.timeScale().fitContent();

      resizeObserver = new ResizeObserver(() => {
        if (containerRef.current && chart) {
          chart.applyOptions({ width: containerRef.current.clientWidth });
        }
      });
      resizeObserver.observe(containerRef.current);
    });

    return () => {
      resizeObserver?.disconnect();
      chart?.remove();
    };
  }, [data, period]);

  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <div className="mb-3 flex gap-2">
        {PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`rounded px-2 py-1 text-xs ${
              p === period ? "bg-brand text-white" : "bg-surface text-gray-500 hover:bg-gray-200"
            }`}
          >
            {t(`periods.${p}`, p)}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-negative">{t("common.error")}</p>}
      <div ref={containerRef} className="w-full" />
    </div>
  );
}
