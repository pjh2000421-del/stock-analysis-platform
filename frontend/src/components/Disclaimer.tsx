"use client";

import { useTranslation } from "@/lib/i18n/I18nProvider";

/** 요구사항 61: 페이지 하단 투자 유의 문구. */
export function Disclaimer() {
  const { t } = useTranslation();
  return (
    <p className="mx-auto max-w-5xl px-4 py-6 text-center text-xs text-gray-400">
      {t("disclaimer")}
    </p>
  );
}
