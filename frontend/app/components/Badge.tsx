import { ReactNode } from "react";

type Tone = "gray" | "green" | "amber" | "red" | "blue";

const tones: Record<Tone, string> = {
  gray: "bg-surface-2 text-ink-2 border-line-strong",
  green: "bg-brand-tint text-brand-strong border-[#bcd7ce]",
  amber: "bg-freight-tint text-freight border-[#e5cbb2]",
  red: "bg-danger-tint text-danger border-[#e6c3bd]",
  // 원장 톤에 맞춘 뮤트 네이비 — 제네릭 블루가 아님.
  blue: "bg-[#e6eaf1] text-[#3a4a63] border-[#cfd7e4]",
};

export default function Badge({
  children,
  tone = "gray",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
