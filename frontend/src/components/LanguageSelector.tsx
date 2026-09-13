"use client";

import { LOCALES, type Locale } from "@/lib/i18n/dictionaries";
import { useTranslation } from "@/lib/i18n/I18nProvider";

const LABELS: Record<Locale, string> = {
  ko: "한국어",
  ja: "日本語",
  en: "English",
};

/** 우측 상단 언어 선택기 (요구사항: 한국어 | 日本語 | English). */
export function LanguageSelector() {
  const { locale, setLocale } = useTranslation();

  return (
    <div className="flex items-center gap-1 text-sm">
      {LOCALES.map((l, idx) => (
        <span key={l} className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setLocale(l)}
            className={
              l === locale
                ? "font-semibold text-white"
                : "text-gray-300 hover:text-white transition-colors"
            }
            aria-current={l === locale}
          >
            {LABELS[l]}
          </button>
          {idx < LOCALES.length - 1 && <span className="text-gray-500">|</span>}
        </span>
      ))}
    </div>
  );
}
