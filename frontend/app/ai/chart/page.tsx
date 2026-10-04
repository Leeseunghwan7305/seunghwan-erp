"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const Markdown = dynamic(() => import("../../components/Markdown"), { ssr: false });
const ToolResultView = dynamic(() => import("../../components/ToolResultView"), { ssr: false });

const EXAMPLES = [
  "월별 주문 건수 추이를 차트로 보여줘",
  "거래처별 미수금을 그래프로",
  "품목별 재고 상위를 차트로 보여줘",
  "매출 vs 매입 비교 차트",
];

export default function ChartAgentPage() {
  const [goal, setGoal] = useState("");
  const [charts, setCharts] = useState<{ name: string; data: unknown }[]>([]);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = () => abortRef.current?.abort();

  const run = async (g: string) => {
    const text = g.trim();
    if (!text || busy) return;
    setCharts([]);
    setAnswer("");
    setErr(null);
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "local", messages: [{ role: "user", content: text }] }),
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
          if (evt.type === "tool_result" && evt.name === "get_chart")
            setCharts((c) => [...c, { name: evt.name, data: evt.data }]);
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
        eyebrow="AI · Text-to-Chart"
        title="자연어 → 차트"
        desc="말로 요청하면 에이전트가 적절한 집계 도구(get_chart)를 골라 데이터를 조회하고, 결과를 막대·선 그래프로 그려줍니다."
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
            placeholder="예) 월별 주문 추이를 차트로 보여줘"
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
              그리기
            </button>
          )}
        </form>
        {charts.length === 0 && !answer && !busy && (
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((g) => (
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

      {err && <div className="rounded-lg border border-danger/40 bg-danger-tint px-4 py-3 text-sm text-danger">⚠️ {err}</div>}
      {busy && charts.length === 0 && (
        <div className="rounded-card border border-line bg-surface p-5 text-sm text-ink-3">데이터를 조회해 차트를 그리는 중…</div>
      )}

      {charts.map((c, i) => (
        <div key={i} className="rounded-card border border-line bg-surface p-5">
          <ToolResultView name={c.name} data={c.data} />
        </div>
      ))}

      {answer && (
        <div className="rounded-card border border-brand/30 bg-brand-tint/40 p-5 text-sm leading-relaxed text-ink">
          <Markdown text={answer} />
        </div>
      )}
    </div>
  );
}
