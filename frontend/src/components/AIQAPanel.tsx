"use client";

import { useState } from "react";

import { useTranslation } from "@/lib/i18n/I18nProvider";
import { api, ApiError } from "@/lib/api";

interface QAMessage {
  question: string;
  answer: string | null;
  isUnavailable: boolean;
  errorMessage: string | null;
}

/**
 * 종목 상세 페이지 우측 AI 질의응답 패널 (byul.ai류 "AI에게 무엇이든 물어보기" 참고).
 *
 * 다른 서비스와 달리 이 패널은 자유 채팅이 아니라, 백엔드가 이 종목의 실제
 * 가격/재무/뉴스 데이터를 Claude에게 함께 전달해 그 데이터에 근거한 답변만
 * 생성하도록 한다 (요구사항 74). 대화 기록은 이 세션(페이지를 새로고침하기
 * 전까지)에만 유지되며 서버에 저장되지 않고, 매 질문은 이전 대화 맥락 없이
 * 독립적으로 처리된다.
 */
export function AIQAPanel({ ticker }: { ticker: string }) {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setLoading(true);
    try {
      const res = await api.askCompanyQuestion(ticker, question);
      setMessages((prev) => [
        ...prev,
        {
          question,
          answer: res.answer,
          isUnavailable: res.is_unavailable,
          errorMessage: res.is_unavailable ? res.message : res.answer ? null : res.message,
        },
      ]);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : t("aiQa.errorGeneric");
      setMessages((prev) => [...prev, { question, answer: null, isUnavailable: false, errorMessage: message }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col rounded border border-gray-200 bg-white">
      <div className="border-b border-gray-100 px-4 py-3">
        <h3 className="font-semibold text-brand">{t("aiQa.title")}</h3>
        <p className="mt-0.5 text-xs text-gray-400">{t("aiQa.subtitle")}</p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3" style={{ minHeight: 200, maxHeight: 480 }}>
        {messages.length === 0 && !loading && (
          <p className="text-sm text-gray-400">{t("aiQa.emptyHint")}</p>
        )}

        {messages.map((m, i) => (
          <div key={i} className="space-y-1.5">
            <div className="ml-auto max-w-[90%] rounded-lg bg-brand px-3 py-1.5 text-sm text-white">
              {m.question}
            </div>
            {m.answer ? (
              <div className="max-w-[90%] whitespace-pre-wrap rounded-lg bg-gray-50 px-3 py-1.5 text-sm text-gray-800">
                {m.answer}
              </div>
            ) : (
              <div className="max-w-[90%] rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-700">
                {m.isUnavailable ? t("aiQa.unavailable") : m.errorMessage ?? t("aiQa.errorGeneric")}
              </div>
            )}
          </div>
        ))}

        {loading && <p className="text-xs text-gray-400">{t("aiQa.thinking")}</p>}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-gray-100 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t("aiQa.placeholder")}
            maxLength={500}
            disabled={loading}
            className="flex-1 rounded border border-gray-300 px-3 py-1.5 text-sm focus:border-brand focus:outline-none disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded bg-brand px-3 py-1.5 text-sm text-white disabled:opacity-40"
          >
            {t("aiQa.send")}
          </button>
        </div>
        <p className="mt-2 text-[11px] leading-snug text-gray-400">{t("aiQa.disclaimer")}</p>
      </form>
    </div>
  );
}
