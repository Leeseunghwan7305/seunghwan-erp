"use client";

/*
  물류 원장 대시보드 차트 — 의존성 없는 경량 SVG/CSS 차트.
  색은 상태/카테고리 역할로만 배정하고, 값은 항상 직접 라벨로 노출한다
  (색만으로 의미를 전달하지 않도록 — 색맹 접근성).
*/

export type Tone = "brand" | "freight" | "danger" | "ink";

const toneVar: Record<Tone, string> = {
  brand: "var(--brand)",
  freight: "var(--freight)",
  danger: "var(--danger)",
  ink: "var(--ink-2)",
};

export interface BarRow {
  label: string;
  value: number;
  tone?: Tone;
  /** 임계선(예: 안전재고) — 있으면 트랙 위에 세로 마커를 그린다 */
  marker?: number;
  /** 값 옆 상태 배지 */
  pill?: { text: string; tone: Tone };
}

/** 가로 막대 차트. 트랙 위에 채움 막대 + 선택적 임계 마커 + 직접 값 라벨. */
export function HBars({
  rows,
  max,
  format,
  labelWidth = "6.5rem",
}: {
  rows: BarRow[];
  max?: number;
  format: (n: number) => string;
  labelWidth?: string;
}) {
  const ceil =
    max ??
    Math.max(1, ...rows.map((r) => Math.max(r.value, r.marker ?? 0))) * 1.08;

  return (
    <div className="flex flex-col gap-3.5">
      {rows.map((r) => {
        const pct = Math.max(0, Math.min(100, (r.value / ceil) * 100));
        const mpct =
          r.marker != null
            ? Math.max(0, Math.min(100, (r.marker / ceil) * 100))
            : null;
        const fill = toneVar[r.tone ?? "brand"];
        return (
          <div
            key={r.label}
            className="group grid items-center gap-3"
            style={{ gridTemplateColumns: `${labelWidth} 1fr auto` }}
          >
            <div
              className="truncate text-[13px] text-ink-2"
              title={r.label}
            >
              {r.label}
            </div>

            {/* 트랙 */}
            <div className="relative h-2.5 rounded-full bg-surface-2">
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-[filter] group-hover:brightness-105"
                style={{
                  width: `${pct}%`,
                  minWidth: r.value > 0 ? 6 : 0,
                  background: fill,
                }}
              />
              {/* 임계 마커 */}
              {mpct != null && (
                <div
                  className="absolute top-1/2 h-[14px] w-px -translate-y-1/2 bg-ink-3"
                  style={{ left: `${mpct}%` }}
                  title={`안전재고 ${format(r.marker!)}`}
                />
              )}
              {/* 호버 툴팁 */}
              <div
                className="pointer-events-none absolute bottom-[calc(100%+6px)] left-0 z-10 hidden whitespace-nowrap rounded-md border border-line bg-surface px-2 py-1 text-[11px] text-ink shadow-sm group-hover:block"
                style={{ left: `min(${pct}%, calc(100% - 4rem))` }}
              >
                <span className="num">{format(r.value)}</span>
                {r.marker != null && (
                  <span className="text-ink-3">
                    {" "}
                    · 안전 <span className="num">{format(r.marker)}</span>
                  </span>
                )}
              </div>
            </div>

            {/* 직접 값 라벨 */}
            <div className="flex items-center justify-end gap-2">
              <span className="num text-[13px] font-medium text-ink">
                {format(r.value)}
              </span>
              {r.pill && <Pill tone={r.pill.tone}>{r.pill.text}</Pill>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Pill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: Tone;
}) {
  const map: Record<Tone, string> = {
    brand: "bg-brand-tint text-brand",
    freight: "bg-freight-tint text-freight",
    danger: "bg-danger-tint text-danger",
    ink: "bg-surface-2 text-ink-2",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium leading-none ${map[tone]}`}
    >
      {children}
    </span>
  );
}

/** 도넛 — 상태 비율(정상/미달 등). 얇은 링, 세그먼트 사이 2px 표면 간격. */
export function Donut({
  segments,
  centerValue,
  centerLabel,
  size = 132,
}: {
  segments: { label: string; value: number; tone: Tone }[];
  centerValue: string;
  centerLabel: string;
  size?: number;
}) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const stroke = 13;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const gap = 2; // px 표면 간격
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={segments.map((s) => `${s.label} ${s.value}`).join(", ")}
        className="shrink-0 -rotate-90"
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--surface-2)"
          strokeWidth={stroke}
        />
        {segments.map((s) => {
          const len = (s.value / total) * c;
          const seg = Math.max(0, len - gap);
          const el = (
            <circle
              key={s.label}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={toneVar[s.tone]}
              strokeWidth={stroke}
              strokeDasharray={`${seg} ${c - seg}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            />
          );
          offset += len;
          return el;
        })}
      </svg>
      <div className="flex flex-col gap-2">
        <div>
          <div className="num text-[26px] font-semibold leading-none text-ink">
            {centerValue}
          </div>
          <div className="mt-1 text-[11px] text-ink-3">{centerLabel}</div>
        </div>
        <div className="mt-1 flex flex-col gap-1.5">
          {segments.map((s) => (
            <div key={s.label} className="flex items-center gap-2 text-[12px]">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm"
                style={{ background: toneVar[s.tone] }}
              />
              <span className="text-ink-2">{s.label}</span>
              <span className="num ml-auto pl-3 text-ink">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** 카드 컨테이너 — 눈썹 라벨 + 우측 보조 텍스트. */
export function Panel({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="eyebrow">{title}</h2>
        {aside && <div className="text-[12px] text-ink-3">{aside}</div>}
      </header>
      {children}
    </section>
  );
}

/** 범례 한 줄. */
export function Legend({
  items,
}: {
  items: { label: string; tone: Tone; kind?: "dot" | "line" }[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-2">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5">
          {it.kind === "line" ? (
            <span
              className="inline-block h-3 w-px"
              style={{ background: "var(--ink-3)" }}
            />
          ) : (
            <span
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: toneVar[it.tone] }}
            />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}
