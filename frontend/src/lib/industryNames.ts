import type { Locale } from "./i18n/dictionaries";

/**
 * WICS 업종명(백엔드가 한국어로 저장) → English / 日本語 표시명.
 *
 * WICS는 GICS와 같은 코드 체계를 쓰므로, 대분류 10개와 백엔드에서 실제로 확인된 소분류
 * (wics_provider.py의 KNOWN_SUB_INDUSTRY_CODES)에 대해 GICS의 공식 영문/일문 명칭을 사용한다.
 * 여기에 없는 이름(예: WICS 조회 실패 시의 KRX 원본 업종명)은 한국어 그대로 보여준다.
 * 소분류를 백엔드에 추가하면 여기에도 함께 추가해야 한다.
 */
const INDUSTRY_NAMES: Record<string, { en: string; ja: string }> = {
  // 대분류 (Sector)
  에너지: { en: "Energy", ja: "エネルギー" },
  소재: { en: "Materials", ja: "素材" },
  산업재: { en: "Industrials", ja: "資本財・サービス" },
  경기관련소비재: { en: "Consumer Discretionary", ja: "一般消費財・サービス" },
  필수소비재: { en: "Consumer Staples", ja: "生活必需品" },
  보건의료: { en: "Health Care", ja: "ヘルスケア" },
  금융: { en: "Financials", ja: "金融" },
  IT: { en: "Information Technology", ja: "情報技術" },
  커뮤니케이션서비스: { en: "Communication Services", ja: "コミュニケーション・サービス" },
  유틸리티: { en: "Utilities", ja: "公益事業" },
  // 소분류 (확인된 항목만)
  반도체와반도체장비: { en: "Semiconductors & Semiconductor Equipment", ja: "半導体・半導体製造装置" },
  자동차와부품: { en: "Automobiles & Components", ja: "自動車・自動車部品" },
  은행: { en: "Banks", ja: "銀行" },
  미디어와엔터테인먼트: { en: "Media & Entertainment", ja: "メディア・娯楽" },
  제약과생물공학: { en: "Pharmaceuticals & Biotechnology", ja: "医薬品・バイオテクノロジー" },
};

export function localizeIndustryName(name: string, locale: Locale): string {
  if (locale === "ko") return name;
  return INDUSTRY_NAMES[name]?.[locale] ?? name;
}
