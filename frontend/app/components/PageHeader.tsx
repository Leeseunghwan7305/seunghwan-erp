import { ReactNode } from "react";

// 모든 화면 상단의 공통 헤더 — mono 눈썹 + 타이틀 + 우측 메타.
export default function PageHeader({
  eyebrow,
  title,
  desc,
  meta,
}: {
  eyebrow: string;
  title: string;
  desc?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="mb-8">
      <div className="eyebrow mb-2">{eyebrow}</div>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <h1 className="text-[26px] font-semibold leading-none tracking-tight text-ink">
          {title}
        </h1>
        {meta && <div className="text-sm text-ink-2">{meta}</div>}
      </div>
      {desc && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-ink-2">{desc}</p>}
    </header>
  );
}
