"use client";

import { useState } from "react";

/** Simple View용 금융 용어 설명 Tooltip (요구사항 24). */
export function Tooltip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block">
      <button
        type="button"
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-gray-400 text-[10px] text-gray-500"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
        aria-label="설명 보기"
      >
        ?
      </button>
      {open && (
        <span className="absolute left-1/2 top-6 z-20 w-64 -translate-x-1/2 whitespace-pre-line rounded border border-gray-200 bg-white p-2 text-xs leading-relaxed text-gray-600 shadow-lg">
          {text}
        </span>
      )}
    </span>
  );
}
