"use client";

import { useEffect, useState } from "react";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Pt {
  label: string;
  type: "item" | "doc";
  x: number;
  y: number;
}

export default function EmbeddingMapPage() {
  const [points, setPoints] = useState<Pt[]>([]);
  const [meta, setMeta] = useState<{ item_count: number; doc_count: number } | null>(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);

  const load = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`${BASE}/rag/embedding-map`);
      if (!res.ok) throw new Error(`서버 오류 (${res.status})`);
      const d = await res.json();
      setPoints(d.points ?? []);
      setMeta({ item_count: d.item_count ?? 0, doc_count: d.doc_count ?? 0 });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  // 0~1 좌표를 패딩 6, 크기 88의 좌표로(스크린은 y 뒤집기)
  const px = (x: number) => 6 + x * 88;
  const py = (y: number) => 6 + (1 - y) * 88;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="AI · Embedding Map"
        title="임베딩 의미 지도"
        desc="품목·문서를 bge-m3로 임베딩(1024차원)한 뒤 2D로 투영(PCA)했어요. 뜻이 비슷할수록 지도 위에서 가까이 모입니다 — RAG가 '의미로 검색'하는 원리를 눈으로 보는 지도."
        meta={
          <button
            onClick={load}
            disabled={busy}
            className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
          >
            {busy ? "계산 중…" : "다시 계산"}
          </button>
        }
      />

      <div className="rounded-card border border-line bg-surface p-5">
        <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-brand" /> 품목 {meta?.item_count ?? 0}개
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-freight" /> 문서 청크 {meta?.doc_count ?? 0}개
          </span>
          <span className="text-ink-3">· 점에 마우스를 올리면 이름이 보여요</span>
        </div>

        {err && <div className="rounded-lg border border-danger/40 bg-danger-tint px-4 py-3 text-sm text-danger">⚠️ {err}</div>}
        {busy && !points.length && (
          <div className="py-16 text-center text-sm text-ink-3">임베딩을 계산하는 중… (몇 초 걸려요)</div>
        )}

        {!!points.length && (
          <div className="relative w-full overflow-hidden rounded-xl border border-line bg-paper">
            <svg viewBox="0 0 100 100" className="w-full" style={{ aspectRatio: "1.6 / 1" }}>
              {/* 옅은 격자 */}
              {[20, 40, 60, 80].map((g) => (
                <g key={g} stroke="var(--line)" strokeWidth="0.15" opacity="0.6">
                  <line x1={g} y1="4" x2={g} y2="96" />
                  <line x1="4" y1={g} x2="96" y2={g} />
                </g>
              ))}
              {points.map((p, i) => (
                <circle
                  key={i}
                  cx={px(p.x)}
                  cy={py(p.y)}
                  r={hover === i ? 2.4 : 1.3}
                  fill={p.type === "item" ? "var(--brand)" : "var(--freight)"}
                  opacity={hover === null || hover === i ? 0.95 : 0.4}
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  style={{ transition: "r .12s, opacity .12s", cursor: "pointer" }}
                />
              ))}
              {hover !== null && (
                <g style={{ pointerEvents: "none" }}>
                  <text
                    x={Math.min(Math.max(px(points[hover].x), 12), 88)}
                    y={py(points[hover].y) - 3.5}
                    textAnchor="middle"
                    fontSize="3"
                    fontWeight="700"
                    fill="var(--ink)"
                    style={{ paintOrder: "stroke", stroke: "var(--surface)", strokeWidth: 1 }}
                  >
                    {points[hover].label}
                  </text>
                </g>
              )}
            </svg>
          </div>
        )}
      </div>

      <div className="rounded-card border border-brand/20 bg-brand-tint/30 p-5 text-sm leading-relaxed text-ink-2">
        <p className="mb-1 font-semibold text-brand-strong">🔍 이 지도를 읽는 법</p>
        <p>
          비슷한 뜻의 항목은 <b>가까이</b>, 다른 건 <b>멀리</b> 놓여요. 예를 들어 음료 품목끼리, 사무용품끼리 뭉쳐 보일 거예요.
          RAG는 질문도 이렇게 점으로 바꾼 뒤 <b>가장 가까운 점(=관련 문서)</b>을 찾아 근거로 씁니다. (실제론 1024차원이라 2D는 ‘그림자’예요)
        </p>
      </div>
    </div>
  );
}
