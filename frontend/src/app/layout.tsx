import type { Metadata } from "next";
import { cookies } from "next/headers";

import "./globals.css";
import { I18nProvider } from "@/lib/i18n/I18nProvider";
import { DEFAULT_LOCALE, LOCALES, type Locale } from "@/lib/i18n/dictionaries";
import { Header } from "@/components/Header";
import { Disclaimer } from "@/components/Disclaimer";

export const metadata: Metadata = {
  title: "한국 주식 AI 분석 플랫폼",
  description: "주가, 재무, 뉴스, 과거 유사 사례, 머신러닝을 연결한 한국 주식 분석 플랫폼",
};

function resolveLocale(value: string | undefined): Locale {
  if (value && (LOCALES as string[]).includes(value)) return value as Locale;
  return DEFAULT_LOCALE;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const cookieLocale = cookies().get("locale")?.value;
  const locale = resolveLocale(cookieLocale);

  return (
    <html lang={locale}>
      <body>
        <I18nProvider initialLocale={locale}>
          <Header />
          <main className="mx-auto min-h-[70vh] max-w-6xl px-4 py-6">{children}</main>
          <Disclaimer />
        </I18nProvider>
      </body>
    </html>
  );
}
