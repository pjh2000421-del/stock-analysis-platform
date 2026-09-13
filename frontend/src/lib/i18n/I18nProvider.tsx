"use client";

/**
 * 경량 i18n Provider.
 *
 * next-intl 등 외부 라이브러리 없이, locales/*.json 딕셔너리 + Context 기반으로
 * 요구사항(다국어 지원, 하드코딩 금지, 선택 언어 cookie 저장)을 충족한다.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { DEFAULT_LOCALE, getDictionary, type Locale } from "./dictionaries";

const LOCALE_COOKIE = "locale";

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, fallback?: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function getByPath(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((acc, part) => {
    if (acc && typeof acc === "object" && part in (acc as Record<string, unknown>)) {
      return (acc as Record<string, unknown>)[part];
    }
    return undefined;
  }, obj);
}

export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale ?? DEFAULT_LOCALE);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    if (typeof document !== "undefined") {
      // 1년간 유지 (요구사항: 다음 접속에서도 언어 설정 유지)
      document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000`;
    }
  }, []);

  const t = useCallback(
    (key: string, fallback?: string) => {
      const dict = getDictionary(locale);
      const value = getByPath(dict, key);
      if (typeof value === "string") return value;
      return fallback ?? key;
    },
    [locale]
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useTranslation은 I18nProvider 내부에서만 사용할 수 있습니다.");
  }
  return ctx;
}
