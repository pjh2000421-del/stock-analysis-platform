import ko from "./locales/ko.json";
import ja from "./locales/ja.json";
import en from "./locales/en.json";

export type Locale = "ko" | "ja" | "en";

export const LOCALES: Locale[] = ["ko", "ja", "en"];
export const DEFAULT_LOCALE: Locale = "ko";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const dictionaries: Record<Locale, any> = { ko, ja, en };

export function getDictionary(locale: Locale) {
  return dictionaries[locale] ?? dictionaries[DEFAULT_LOCALE];
}
