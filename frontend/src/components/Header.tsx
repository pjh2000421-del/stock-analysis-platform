"use client";

import Link from "next/link";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { LanguageSelector } from "@/components/LanguageSelector";
import { SearchBar } from "@/components/SearchBar";

/** 전역 상단 네비게이션 (요구사항 4, 다국어 Language Selector 포함). */
export function Header() {
  const { t } = useTranslation();

  const links = [
    { href: "/", labelKey: "nav.dashboard" },
    { href: "/watchlist", labelKey: "nav.watchlist" },
    { href: "/analysis-lab", labelKey: "nav.analysisLab" },
    { href: "/simulation-lab", labelKey: "nav.simulationLab" },
    { href: "/about", labelKey: "nav.about" },
  ];

  return (
    <header className="bg-brand text-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-lg font-bold whitespace-nowrap">
            {t("common.appName")}
          </Link>
          <nav className="hidden gap-4 text-sm text-gray-200 sm:flex">
            {links.map((l) => (
              <Link key={l.href} href={l.href} className="hover:text-white">
                {t(l.labelKey)}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <SearchBar />
          <LanguageSelector />
        </div>
      </div>
      <nav className="flex gap-4 overflow-x-auto bg-brand-light px-4 py-2 text-sm text-gray-100 sm:hidden">
        {links.map((l) => (
          <Link key={l.href} href={l.href} className="whitespace-nowrap hover:text-white">
            {t(l.labelKey)}
          </Link>
        ))}
      </nav>
    </header>
  );
}
