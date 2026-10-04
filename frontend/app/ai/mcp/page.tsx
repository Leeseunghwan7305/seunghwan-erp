"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const Markdown = dynamic(() => import("../../components/Markdown"), { ssr: false });
const ToolResultView = dynamic(() => import("../../components/ToolResultView"), { ssr: false });

const STEP_LABEL: Record<string, string> = {
  get_inventory: "📊 재고 조회",
  get_dashboard: "📊 현황 지표 조회",
  list_orders: "📊 주문 조회",
  list_partners: "📊 거래처 조회",
  search_documents: "📄 사내 문서 검색",
};

interface Step {
  name: string;
  data?: unknown;
}

const GOALS = [
  "안전재고 미달 품목과 전체 현황 알려줘",
  "거래처와 미수금 상황을 정리해줘",
  "지금 재고가 위험한 품목만 골라줘",
];

export default function McpAgentPage() {
  const [goal, setGoal] = useState("");
  const [discovered, setDiscovered] = useState<string[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = () => abortRef.current?.abort();

  const run = async (g: string) => {
    const text = g.trim();
    if (!text || busy) return;
    setDiscovered([]);
    setSteps([]);
    setAnswer("");
    setErr(null);
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch(`${BASE}/agent/mcp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: text }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`서버 오류 (${res.status})`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
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
          if (evt.type === "discover") setDiscovered(evt.tools ?? []);
          else if (evt.type === "tool") setSteps((s) => [...s, { name: evt.name }]);
          else if (evt.type === "tool_result")
            setSteps((s) => {
              const copy = [...s];
              for (let i = copy.length - 1; i >= 0; i--) {
                if (copy[i].name === evt.name && copy[i].data === undefined) {
                  copy[i] = { ...copy[i], data: evt.data };
                  return copy;
                }
              }
              return [...copy, { name: evt.name, data: evt.data }];
            });
          else if (evt.type === "text") setAnswer((a) => a + evt.content);
          else if (evt.type === "error") setErr(evt.content);
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setErr((e as Error).message);
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="AI · MCP Agent"
        title="MCP 에이전트"
        desc="에이전트가 MCP 서버에 접속해 도구를 런타임에 '발견'하고, MCP 프로토콜로 호출해 목표를 수행합니다. (우리 ERP를 MCP 서버로 노출한 것과 대칭 — 이번엔 소비자)"
      />

      <div className="rounded-card border border-line bg-surface p-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run(goal);
          }}
          className="flex gap-2"
        >
          <input
            className="flex-1 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
            placeholder="예) 안전재고 미달 품목과 전체 현황 알려줘"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            disabled={busy}
          />
          {busy ? (
            <button
              type="button"
              onClick={stop}
              className="inline-flex items-center gap-2 rounded-lg border border-danger/50 bg-danger-tint px-5 py-3 text-sm font-medium text-danger hover:bg-danger/10"
            >
              <span className="h-2.5 w-2.5 rounded-[2px] bg-danger" /> 중지
            </button>
          ) : (
            <button
              type="submit"
              disabled={!goal.trim()}
              className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
            >
              실행
            </button>
          )}
        </form>
        {steps.length === 0 && !answer && !busy && (
          <div className="mt-3 flex flex-wrap gap-2">
            {GOALS.map((g) => (
              <button
                key={g}
                onClick={() => {
                  setGoal(g);
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

      {err && (
        <div className="rounded-lg border border-danger/40 bg-danger-tint px-4 py-3 text-sm text-danger">⚠️ {err}</div>
      )}

      {/* 발견된 MCP 도구 */}
      {discovered.length > 0 && (
        <div className="rounded-card border border-line bg-surface p-5">
          <p className="eyebrow mb-2">🔌 MCP 서버에서 발견한 도구 ({discovered.length})</p>
          <div className="flex flex-wrap gap-1.5">
            {discovered.map((t) => (
              <span
                key={t}
                className="rounded-full border border-brand/40 bg-brand-tint px-2.5 py-1 font-mono text-[12px] text-brand-strong"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 실행 단계 */}
      {(steps.length > 0 || (busy && discovered.length > 0)) && (
        <div className="rounded-card border border-line bg-surface p-5">
          <p className="eyebrow mb-3">실행 단계 (MCP 호출)</p>
          <ol className="space-y-3">
            {steps.map((s, i) => (
              <li key={i} className="border-l-2 border-brand/40 pl-3">
                <div className="mb-1 flex items-center gap-2 text-sm font-medium text-ink">
                  <span className="font-mono text-xs text-ink-3">{i + 1}</span>
                  {STEP_LABEL[s.name] ?? `🔧 ${s.name}`}
                  {s.data === undefined && (
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-line border-t-brand" />
                  )}
                </div>
                {s.data !== undefined && <ToolResultView name={s.name} data={s.data} />}
              </li>
            ))}
            {busy && answer === "" && <li className="pl-3 text-sm text-ink-3">도구를 호출하는 중…</li>}
          </ol>
        </div>
      )}

      {answer && (
        <div className="rounded-card border border-brand/30 bg-brand-tint/40 p-5">
          <p className="eyebrow mb-3 text-brand-strong">✅ 답변</p>
          <div className="text-sm leading-relaxed text-ink">
            <Markdown text={answer} />
          </div>
        </div>
      )}
    </div>
  );
}
