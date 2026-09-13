"use client";

import { useTranslation } from "@/lib/i18n/I18nProvider";

/** About / Methodology 페이지 (요구사항 56). */
export default function AboutPage() {
  const { t } = useTranslation();

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-bold text-brand">{t("aboutPage.title")}</h1>
      <p className="text-sm leading-relaxed text-gray-600">{t("aboutPage.philosophy")}</p>
      <p className="text-sm leading-relaxed text-gray-500">{t("disclaimer")}</p>
    </div>
  );
}
