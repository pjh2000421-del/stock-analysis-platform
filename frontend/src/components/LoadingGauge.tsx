"use client";

import { useEffect, useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";

/**
 * 오래 걸릴 수 있는 첫 로딩용 게이지.
 *
 * 서버는 진행률을 알려주지 않으므로 퍼센트를 꾸며내지 않고, 움직이는 막대(진행 중 표시)와
 * 경과 시간을 보여준다. 기다린 시간에 따라 안내 문구를 바꿔서, 처음 조회하는 기업이거나
 * 무료 서버가 잠에서 깨어나는 중이라 오래 걸릴 수 있다는 것을 알려준다.
 */
export function LoadingGauge() {
  const { t } = useTranslation();
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);

  const messageKey =
    seconds < 5 ? "loadingGauge.initial" : seconds < 20 ? "loadingGauge.firstFetch" : "loadingGauge.wakingUp";

  return (
    <div className="mx-auto max-w-md py-16" role="status" aria-live="polite">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
        <div className="loading-gauge-bar h-full w-1/3 rounded-full bg-brand" />
      </div>
      <div className="mt-3 flex items-baseline justify-between gap-4 text-sm">
        <span className="text-gray-600">{t(messageKey)}</span>
        <span className="tabular-num shrink-0 text-gray-400">
          {t("loadingGauge.elapsed", undefined, { seconds })}
        </span>
      </div>
    </div>
  );
}
