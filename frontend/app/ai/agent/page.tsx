"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const Markdown = dynamic(() => import("../../components/Markdown"), { ssr: false });
const ToolResultView = dynamic(() => import("../../components/ToolResultView"), { ssr: false });

// 도구 → 단계 라벨
const STEP_LABEL: Record<string, string> = {
  get_inventory: "📊 재고 조회",
  get_dashboard: "📊 현황 지표 조회",
  list_orders: "📊 주문 조회",
  list_partners: "📊 거래처 조회",
  search_documents: "📄 사내 문서 검색",
  doc_context: "📄 사내 문서 참조",
  web_search: "🌐 웹 검색",
};

interface Step {
  name: string;
  data?: unknown;
}

const GOALS = [
  "이번 달 재고 리스크 브리핑 (미달 품목·전체 현황 포함)",
  "거래처·미수금 현황을 요약해줘",
  "지금 주의가 필요한 재고와 진행 중 주문을 정리해줘",
];

export default function AgentBriefPage() {
  const [model, setModel] = useState<"claude" | "local">("local");
  const [goal, setGoal] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [briefing, setBriefing] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = () => abortRef.current?.abort();

  const run = async (g: string) => {
    const text = g.trim();
    if (!text || busy) return;
    setSteps([]);
    setBriefing("");
    setErr(null);
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${BASE}/agent/brief`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, goal: text }),
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
          if (evt.type === "tool") {
            if (evt.name === "doc_context") continue; // 자동 주입은 단계로 표시하지 않음
            setSteps((s) => [...s, { name: evt.name }]);
          } else if (evt.type === "tool_result") {
            setSteps((s) => {
              const copy = [...s];
              // 가장 최근의 같은 이름·데이터 없는 단계에 결과를 붙인다.
              for (let i = copy.length - 1; i >= 0; i--) {
                if (copy[i].name === evt.name && copy[i].data === undefined) {
                  copy[i] = { ...copy[i], data: evt.data };
                  return copy;
                }
              }
              return [...copy, { name: evt.name, data: evt.data }];
            });
          } else if (evt.type === "text") {
            setBriefing((b) => b + evt.content);
          } else if (evt.type === "error") {
            setErr(evt.content);
          }
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
        eyebrow="AI · Agent"
        title="브리핑 에이전트"
        desc="목표를 주면 에이전트가 필요한 데이터를 스스로 여러 번 조회해 모은 뒤, 구조화된 브리핑으로 종합합니다. (읽기 전용)"
        meta={
          <div className="inline-flex overflow-hidden rounded-md border border-line text-sm">
            {(["claude", "local"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setModel(m)}
                disabled={busy}
                className={`px-4 py-1.5 transition-colors disabled:opacity-50 ${
                  model === m ? "bg-brand text-white" : "bg-surface text-ink-2 hover:text-ink"
                }`}
              >
                {m === "claude" ? "Claude" : "로컬 LLM"}
              </button>
            ))}
          </div>
        }
      />

      {/* 목표 입력 */}
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
            placeholder="예) 이번 달 재고 리스크 브리핑 만들어줘"
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
              브리핑 생성
            </button>
          )}
        </form>
        {steps.length === 0 && !briefing && !busy && (
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

      {/* 단계 트레이스 */}
      {(steps.length > 0 || busy) && (
        <div className="rounded-card border border-line bg-surface p-5">
          <p className="eyebrow mb-3">수집 단계</p>
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
            {busy && briefing === "" && (
              <li className="pl-3 text-sm text-ink-3">데이터를 수집하는 중…</li>
            )}
          </ol>
        </div>
      )}

      {/* 브리핑 결과 */}
      {briefing && (
        <div className="rounded-card border border-brand/30 bg-brand-tint/40 p-5">
          <p className="eyebrow mb-3 text-brand-strong">📋 브리핑</p>
          <div className="text-sm leading-relaxed text-ink">
            <Markdown text={briefing} />
          </div>
        </div>
      )}
    </div>
  );
}
