"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const Markdown = dynamic(() => import("../../components/Markdown"), { ssr: false });

const SOURCE: Record<string, string> = {
  web_search: "🌐 웹",
  search_documents: "📄 문서",
  doc_context: "📄 문서",
  get_dashboard: "📊 ERP",
  get_inventory: "📊 ERP",
  get_chart: "📊 ERP",
  list_orders: "📊 ERP",
  list_partners: "📊 ERP",
};

interface Side {
  model: string;
  answer: string;
  tools: string[];
  ttft: number | null; // 첫 토큰까지(ms)
  total: number | null; // 완료까지(ms)
  busy: boolean;
}

const EXAMPLES = [
  "안전재고가 뭔지 설명해줘",
  "탄산수 재고 얼마나 있어?",
  "비트코인 시세 알려줘",
];

const MODELS = { A: "qwen2.5:7b", B: "qwen2.5:3b" };

function blank(model: string): Side {
  return { model, answer: "", tools: [], ttft: null, total: null, busy: false };
}

export default function ArenaPage() {
  const [q, setQ] = useState("");
  const [a, setA] = useState<Side>(blank(MODELS.A));
  const [b, setB] = useState<Side>(blank(MODELS.B));
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const streamOne = async (
    model: string,
    setSide: React.Dispatch<React.SetStateAction<Side>>,
    question: string,
    signal: AbortSignal
  ) => {
    const start = performance.now();
    setSide({ ...blank(model), busy: true });
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "local", local_model: model, messages: [{ role: "user", content: question }] }),
        signal,
      });
      if (!res.ok || !res.body) throw new Error(`서버 오류 (${res.status})`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let firstToken = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const evt = JSON.parse(line.slice(5).trim());
          if (evt.type === "tool") setSide((s) => ({ ...s, tools: [...s.tools, evt.name] }));
          else if (evt.type === "text") {
            if (!firstToken) {
              firstToken = true;
              const t = performance.now() - start;
              setSide((s) => ({ ...s, ttft: t }));
            }
            setSide((s) => ({ ...s, answer: s.answer + evt.content }));
          } else if (evt.type === "error") setSide((s) => ({ ...s, answer: `⚠️ ${evt.content}` }));
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setSide((s) => ({ ...s, answer: `⚠️ ${(e as Error).message}` }));
    } finally {
      const total = performance.now() - start;
      setSide((s) => ({ ...s, total, busy: false }));
    }
  };

  const run = async (question: string) => {
    const text = question.trim();
    if (!text || running) return;
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;
    await Promise.all([
      streamOne(MODELS.A, setA, text, controller.signal),
      streamOne(MODELS.B, setB, text, controller.signal),
    ]);
    abortRef.current = null;
    setRunning(false);
  };

  const badges = (tools: string[]) => {
    const set = new Set(tools.map((t) => SOURCE[t] ?? t));
    return Array.from(set);
  };

  const fmtMs = (ms: number | null) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)}s`);

  const Column = ({ side, label }: { side: Side; label: string }) => (
    <div className="flex flex-1 flex-col rounded-card border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-sm font-semibold text-ink">{label}</span>
        <span className="font-mono text-xs text-ink-2">{side.model}</span>
      </div>
      <div className="mb-3 flex gap-3 text-xs">
        <span className="rounded-md bg-surface-2 px-2 py-1">
          첫 응답 <b className="font-mono text-brand-strong">{fmtMs(side.ttft)}</b>
        </span>
        <span className="rounded-md bg-surface-2 px-2 py-1">
          완료 <b className="font-mono text-brand-strong">{fmtMs(side.total)}</b>
        </span>
        <span className="rounded-md bg-surface-2 px-2 py-1">
          글자 <b className="font-mono text-brand-strong">{side.answer.length}</b>
        </span>
      </div>
      {badges(side.tools).length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1">
          {badges(side.tools).map((lbl, i) => (
            <span key={i} className="rounded-full border border-line px-2 py-0.5 font-mono text-[11px] text-ink-2">
              {lbl}
            </span>
          ))}
        </div>
      )}
      <div className="min-h-[4rem] text-sm leading-relaxed text-ink">
        {side.answer && !side.answer.startsWith("⚠️") ? (
          <Markdown text={side.answer} />
        ) : side.answer ? (
          <span className="whitespace-pre-wrap text-danger">{side.answer}</span>
        ) : side.busy ? (
          <span className="text-ink-3">생성 중…</span>
        ) : (
          <span className="text-ink-3">—</span>
        )}
      </div>
    </div>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="AI · Model Arena"
        title="모델 아레나"
        desc="같은 질문을 두 로컬 모델(qwen2.5 7B vs 3B)에 동시에 던져 속도·답변·근거를 나란히 비교합니다. 모델 크기 트레이드오프를 눈으로."
      />

      <div className="rounded-card border border-line bg-surface p-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(q);
          }}
          className="flex gap-2"
        >
          <input
            className="flex-1 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
            placeholder="예) 안전재고가 뭔지 설명해줘"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            disabled={running}
          />
          <button
            type="submit"
            disabled={running || !q.trim()}
            className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {running ? "대결 중…" : "대결"}
          </button>
        </form>
        {!running && !a.answer && !b.answer && (
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((g) => (
              <button
                key={g}
                onClick={() => {
                  setQ(g);
                  run(g);
                }}
                className="rounded-full border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand"
              >
                {g}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4 md:flex-row">
        <Column side={a} label="🅰 7B (크고 느림)" />
        <Column side={b} label="🅱 3B (작고 빠름)" />
      </div>

      <p className="text-xs text-ink-3">
        * 같은 질문·같은 도구를 쓰되 모델만 다릅니다. 보통 3B가 <b>빠르지만</b>, 라우팅·근거 선택은 7B가 더 안정적입니다 — 이 트레이드오프를 직접 보기 위한 아레나예요.
      </p>
    </div>
  );
}
