"use client";

import type { FormEvent, RefObject } from "react";

interface ChatComposerProps {
  value: string;
  placeholder: string;
  disabled: boolean;
  canSubmit: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}

export default function ChatComposer({
  value,
  placeholder,
  disabled,
  canSubmit,
  inputRef,
  onChange,
  onSubmit,
}: ChatComposerProps) {
  return (
    <div className="border-t border-[#cddcea] dark:border-[#162840] bg-[#f4f8fd] dark:bg-[#091524] px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:p-4">
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="min-w-0 flex-1 bg-white dark:bg-[#0d1c2e] border border-[#cddcea] dark:border-[#162840] hover:border-[#b0c8e0] dark:hover:border-[#1e3858] focus:border-[#1a4a8a] dark:focus:border-[#4a7fc8] focus:ring-1 focus:ring-[#1a4a8a]/15 dark:focus:ring-[#4a7fc8]/15 rounded-xl px-3 py-2.5 text-sm text-[#0a1e38] dark:text-[#c4d8f0] placeholder-[#94b0cc] dark:placeholder-[#3d5878] focus:outline-none disabled:opacity-40 transition-all shadow-sm md:px-4"
        />
        <button
          type="submit"
          disabled={!canSubmit}
          className="bg-[#1a4a8a] hover:bg-[#20579e] active:bg-[#143870] disabled:opacity-40 text-white rounded-xl px-4 py-2.5 text-sm font-semibold transition-all shrink-0 shadow-sm shadow-[#1a4a8a]/25 disabled:shadow-none md:px-5"
        >
          Send
        </button>
      </form>
      <p className="text-[10px] text-[#94b0cc] dark:text-[#3d5878] mt-2 text-center font-mono">
        Answers based on FY2023-FY2025 annual reports only.
      </p>
    </div>
  );
}
