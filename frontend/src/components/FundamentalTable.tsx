"use client";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { formatNumber } from "@/lib/format";
import { Tooltip } from "@/components/Tooltip";
import type { ValueWithSource } from "@/types/api";

interface Row {
  labelKey: string;
  glossaryKey?: string;
  value: ValueWithSource;
  suffix?: string;
}

/**
 * 용어 정의에 더해, 수치가 낮을 때/높을 때 각각 무엇을 의미하는지도 함께 보여준다
 * (요구사항: Pro View 물음표 설명 보강). `<key>Low`/`<key>High` 키가 없는 항목은
 * 기존처럼 정의 문장만 표시한다.
 */
function glossaryText(t: (k: string, f?: string) => string, glossaryKey: string): string {
  const def = t(`glossary.${glossaryKey}`);
  const low = t(`glossary.${glossaryKey}Low`, "");
  const high = t(`glossary.${glossaryKey}High`, "");
  if (!low && !high) return def;
  return [
    def,
    "",
    `${t("glossary.lowLabel", "낮으면")}: ${low}`,
    `${t("glossary.highLabel", "높으면")}: ${high}`,
  ].join("\n");
}

/**
 * Valuation/Profitability/Growth/Financial Health 공통 표 (요구사항 18).
 * rows가 아직 null(데이터 로딩 중)이어도 카드/제목 틀은 즉시 렌더링하고,
 * 내부에는 표 형태의 자리표시자 + "불러오는 중" 메세지를 보여준다.
 */
export function FundamentalTable({ title, rows }: { title: string; rows: Row[] | null }) {
  const { t, locale } = useTranslation();

  return (
    <div className="rounded border border-gray-200 bg-white p-4">
      <h3 className="mb-3 font-semibold text-brand">{title}</h3>
      {rows === null ? (
        <div>
          <table className="w-full text-sm">
            <tbody>
              {[0, 1, 2, 3].map((i) => (
                <tr key={i} className="border-b border-gray-100 last:border-0">
                  <td className="py-2">
                    <div className="h-3 w-24 animate-pulse rounded bg-gray-100" />
                  </td>
                  <td className="py-2">
                    <div className="ml-auto h-3 w-12 animate-pulse rounded bg-gray-100" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-gray-400">{t("common.loading")}</p>
        </div>
      ) : (
        <table className="w-full text-sm">
          <tbody>
            {rows.map((row) => (
              <tr key={row.labelKey} className="border-b border-gray-100 last:border-0">
                <td className="py-2 text-gray-500">
                  {t(row.labelKey)}
                  {row.glossaryKey && <Tooltip text={glossaryText(t, row.glossaryKey)} />}
                </td>
                <td className="py-2 tabular-num font-medium">
                  {row.value.is_deficit ? (
                    <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700">
                      {row.value.na_reason ?? t("common.notAvailable")}
                    </span>
                  ) : row.value.is_na ? (
                    t("common.notAvailable")
                  ) : (
                    <>
                      {`${formatNumber(row.value.value, locale, 1)}${row.suffix ?? ""}`}
                      {row.value.meta?.is_estimated && (
                        <span className="ml-1 text-xs font-normal text-gray-400">
                          ({t("common.estimated")})
                        </span>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
