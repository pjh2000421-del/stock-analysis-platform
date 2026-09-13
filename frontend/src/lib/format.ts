/**
 * Locale에 맞는 숫자/날짜/통화 포맷 유틸.
 */
import type { Locale } from "./i18n/dictionaries";

const INTL_LOCALE_MAP: Record<Locale, string> = {
  ko: "ko-KR",
  ja: "ja-JP",
  en: "en-US",
};

export function formatDate(date: string | Date, locale: Locale): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return "-";
  return new Intl.DateTimeFormat(INTL_LOCALE_MAP[locale], {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(d);
}

export function formatNumber(value: number | null | undefined, locale: Locale, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return new Intl.NumberFormat(INTL_LOCALE_MAP[locale], {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number | null | undefined, locale: Locale, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, locale, digits)}%`;
}

/**
 * 원화(KRW) 기준 금액을 locale에 맞는 화폐 단위로 표시한다.
 * 한국어: "72,300원", 일본어: "72,300ウォン", 영어: "KRW 72,300"
 */
export function formatKrwAmount(value: number | null | undefined, locale: Locale): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const formatted = formatNumber(value, locale, 0);
  if (locale === "ko") return `${formatted}원`;
  if (locale === "ja") return `${formatted}ウォン`;
  return `KRW ${formatted}`;
}

/**
 * 시가총액처럼 자릿수가 매우 큰 금액을 읽기 쉬운 단위로 표시한다.
 * 한국어/일본어: "조/억" (兆/億) 단위 (예: "1,517조 1,092억원")
 * 영어: 조 단위(Trillion)/십억(Billion) 약어 (예: "KRW 1.52T")
 * 값이 억(1e8) 미만인 경우 formatKrwAmount와 동일하게 전체 숫자를 표시한다.
 */
export function formatKrwLargeAmount(value: number | null | undefined, locale: Locale): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";

  const TRILLION = 1e12; // 조 / 兆
  const HUNDRED_MILLION = 1e8; // 억 / 億

  if (locale === "en") {
    if (value >= TRILLION) return `KRW ${(value / TRILLION).toFixed(2)}T`;
    if (value >= 1e9) return `KRW ${(value / 1e9).toFixed(2)}B`;
    if (value >= 1e6) return `KRW ${(value / 1e6).toFixed(2)}M`;
    return formatKrwAmount(value, locale);
  }

  if (value < HUNDRED_MILLION) return formatKrwAmount(value, locale);

  const jeUnit = locale === "ja" ? "兆" : "조";
  const eokUnit = locale === "ja" ? "億" : "억";
  const currencySuffix = locale === "ja" ? "ウォン" : "원";

  const rounded = Math.round(value);
  const jo = Math.floor(rounded / TRILLION);
  const eok = Math.floor((rounded % TRILLION) / HUNDRED_MILLION);

  const parts: string[] = [];
  if (jo > 0) parts.push(`${formatNumber(jo, locale, 0)}${jeUnit}`);
  if (eok > 0) parts.push(`${formatNumber(eok, locale, 0)}${eokUnit}`);

  return `${parts.join(" ")}${currencySuffix}`;
}
