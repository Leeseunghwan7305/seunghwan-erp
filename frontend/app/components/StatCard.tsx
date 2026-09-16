type Accent = "red" | "amber" | "green" | "blue";

// 재고 태그 은유: 좌측 상태 스파인 + mono tabular 숫자.
const accents: Record<Accent, { bar: string; text: string }> = {
  green: { bar: "bg-brand", text: "text-brand" },
  amber: { bar: "bg-freight", text: "text-freight" },
  red: { bar: "bg-danger", text: "text-danger" },
  blue: { bar: "bg-ink", text: "text-ink" },
};

export default function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: Accent;
}) {
  const a = accent ? accents[accent] : { bar: "bg-line-strong", text: "text-ink" };
  return (
    <div className="group relative overflow-hidden rounded-card border border-line bg-surface p-5 transition-colors hover:border-line-strong">
      {/* 상태 스파인 */}
      <span className={`absolute inset-y-0 left-0 w-[3px] ${a.bar}`} />
      <div className="mb-3 font-mono text-[11px] tracking-wide text-ink-3">
        {label}
      </div>
      <div className={`num text-[27px] font-semibold leading-none ${a.text}`}>
        {value}
      </div>
      {hint && <div className="mt-2.5 text-xs text-ink-2">{hint}</div>}
    </div>
  );
}
