"use client";

import { useEffect, useRef, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api } from "@/lib/api";
import type { EventMarker, PriceHistoryResponse } from "@/types/api";

const PERIODS = ["1D", "5D", "1M", "3M", "6M", "1Y", "5Y", "MAX"] as const;

// 차트 위 Marker에 뉴스 제목을 그대로 잘라붙이면(예: 12자 truncate) 여러 건이 겹칠 때
// 화면이 매우 지저분해진다. event_type이 있으면 "공급계약"/"실적" 같은 한 단어짜리
// 분류 라벨로 압축해서 보여주고, 전체 제목은 마우스오버 시 Tooltip으로만 보여준다.
function markerShortLabel(m: EventMarker, t: (k: string, f?: string) => string): string {
  if (m.event_type) {
    const label = t(`eventTypes.${m.event_type}`, "");
    if (label) return label;
  }
  return m.title.slice(0, 6);
}

// lightweight-charts는 "yyyy-mm-dd" 문자열로 넣은 시간을 내부적으로 BusinessDay 객체
// ({year, month, day})로 정규화해서 돌려줄 수 있다. crosshairMove의 param.time과
// EventMarker.date(문자열)를 같은 키로 비교하려면 항상 "yyyy-mm-dd" 문자열로 맞춰야 한다.
function timeToDateKey(time: unknown): string | null {
  if (typeof time === "string") return time;
  if (typeof time === "number") return null; // UTCTimestamp(일중 데이터) - 이 차트는 일봉만 쓰므로 해당 없음
  if (time && typeof time === "object" && "year" in time && "month" in time && "day" in time) {
    const bd = time as { year: number; month: number; day: number };
    return `${bd.year}-${String(bd.month).padStart(2, "0")}-${String(bd.day).padStart(2, "0")}`;
  }
  return null;
}

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
  const [hoverTooltip, setHoverTooltip] = useState<{ x: number; y: number; markers: EventMarker[] } | null>(null);
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
            text: markerShortLabel(m, t),
          }))
        );

        // 날짜별로 뉴스 Marker를 모아두고, crosshair(마우스오버)가 그 날짜 위에 오면
        // 해당 날짜의 전체 뉴스 제목을 Tooltip으로 띄운다 - Marker 자체에는 압축된
        // 한 단어 라벨만 남기고, 전체 정보는 hover로만 노출해 차트가 지저분해지지 않게 한다.
        const markersByTime = new Map<string, EventMarker[]>();
        for (const m of data.event_markers) {
          const key = timeToDateKey(m.date);
          if (!key) continue;
          const arr = markersByTime.get(key);
          if (arr) arr.push(m);
          else markersByTime.set(key, [m]);
        }

        chart.subscribeCrosshairMove((param) => {
          const key = param.time ? timeToDateKey(param.time) : null;
          if (!key || !param.point) {
            setHoverTooltip(null);
            return;
          }
          const markers = markersByTime.get(key);
          if (!markers || markers.length === 0) {
            setHoverTooltip(null);
            return;
          }
          setHoverTooltip({ x: param.point.x, y: param.point.y, markers });
        });
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
      setHoverTooltip(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      <div className="relative w-full">
        <div ref={containerRef} className="w-full" />
        {hoverTooltip && (
          <div
            className="pointer-events-none absolute z-10 max-w-[260px] rounded border border-gray-200 bg-white p-2 text-xs shadow-lg"
            style={{
              left: Math.min(
                hoverTooltip.x + 12,
                Math.max((containerRef.current?.clientWidth ?? 0) - 260 - 8, 0)
              ),
              top: Math.max(hoverTooltip.y - 8, 0),
            }}
          >
            {hoverTooltip.markers.map((m) => (
              <div key={m.news_id} className="mb-1 last:mb-0">
                {m.event_type && (
                  <span className="mr-1 rounded bg-surface px-1 text-[10px] text-gray-500">
                    {t(`eventTypes.${m.event_type}`, m.event_type)}
                  </span>
                )}
                <span className="text-gray-700">{m.title}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
