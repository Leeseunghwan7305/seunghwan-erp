"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const Markdown = dynamic(() => import("../../components/Markdown"), { ssr: false });

const SRC_LABEL: Record<string, string> = { web: "🌐 웹", doc: "📄 문서", db: "📊 ERP", none: "— 없음" };

interface Case {
  id: string;
  question: string;
  expect: string;
  actual: string;
  routing_ok: boolean;
  content_ok: boolean;
  ok: boolean;
  preview: string;
}

export default function SelfImprovePage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<{ passed: number; total: number } | null>(null);
  const [diagnosis, setDiagnosis] = useState("");
  const [phase, setPhase] = useState<"idle" | "eval" | "diagnose" | "done">("idle");
  const abortRef = useRef<AbortController | null>(null);

  const run = async () => {
    setCases([]);
    setTotal(0);
    setSummary(null);
    setDiagnosis("");
    setPhase("eval");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch(`${BASE}/agent/self-improve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "local" }),
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
          switch (evt.type) {
            case "eval_start":
              setTotal(evt.total);
              break;
            case "case":
              setCases((cs) => [...cs, evt as Case]);
              break;
            case "eval_done":
              setSummary({ passed: evt.passed, total: evt.total });
              break;
            case "diagnose_start":
              setPhase("diagnose");
              break;
            case "text":
              setDiagnosis((d) => d + evt.content);
              break;
            case "error":
              setDiagnosis((d) => d + `\n\n⚠️ ${evt.content}`);
              break;
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setDiagnosis((d) => d + `\n\n⚠️ ${(e as Error).message}`);
    } finally {
      abortRef.current = null;
      setPhase("done");
    }
  };

  const running = phase === "eval" || phase === "diagnose";
  const pct = summary ? Math.round((100 * summary.passed) / summary.total) : null;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="AI · Self-Improving Loop"
        title="자가 개선 루프"
        desc="골든셋 평가를 돌려 라우팅 회귀를 찾고, LLM이 스스로 근본 원인을 진단해 고칠 레버(임계값·프롬프트·웹폴백)를 제안합니다. 측정 → 자기 진단 → 개선안의 폐루프."
      />

      <div className="rounded-card border border-line bg-surface p-5">
        <div className="flex items-center justify-between gap-4">
          <div className="text-sm text-ink-2">
            <b className="text-ink">측정 문화 + 메타 추론.</b> 답변이 아니라 <i>근거 경로</i>(웹/문서/ERP)를 채점해
            회귀를 잡고, 실패를 LLM에 넘겨 수정안을 받습니다.
          </div>
          <button
            onClick={run}
            disabled={running}
            className="shrink-0 rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {phase === "eval" ? "평가 중…" : phase === "diagnose" ? "진단 중…" : "루프 실행"}
          </button>
        </div>
      </div>

      {(cases.length > 0 || phase === "eval") && (
        <div className="rounded-card border border-line bg-surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="font-mono text-sm font-semibold text-ink">1 · 골든셋 평가</span>
            <span className="font-mono text-xs text-ink-2">
              {cases.length}/{total || "…"}
              {summary && (
                <>
                  {" · "}
                  <b className={pct === 100 ? "text-brand-strong" : "text-freight"}>
                    {summary.passed}/{summary.total} 통과 ({pct}%)
                  </b>
                </>
              )}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-ink-3">
                  <th className="py-2 pr-3 font-medium">결과</th>
                  <th className="py-2 pr-3 font-medium">ID</th>
                  <th className="py-2 pr-3 font-medium">질문</th>
                  <th className="py-2 pr-3 font-medium">기대 근거</th>
                  <th className="py-2 pr-3 font-medium">실제 근거</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr
                    key={c.id}
                    className={`border-b border-line/60 ${c.ok ? "" : "bg-danger-tint"}`}
                  >
                    <td className="py-2 pr-3">{c.ok ? "✅" : "❌"}</td>
                    <td className="py-2 pr-3 font-mono text-xs text-ink-2">{c.id}</td>
                    <td className="py-2 pr-3 text-ink">{c.question}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{SRC_LABEL[c.expect] ?? c.expect}</td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {SRC_LABEL[c.actual] ?? (c.actual || "— 없음")}
                      {!c.routing_ok && <span className="ml-1 text-danger">라우팅✗</span>}
                      {c.routing_ok && !c.content_ok && <span className="ml-1 text-freight">내용✗</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {(diagnosis || phase === "diagnose") && (
        <div className="rounded-card border border-line bg-surface p-5">
          <div className="mb-3 flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-ink">2 · 자가 진단 &amp; 개선안</span>
            {phase === "diagnose" && <span className="text-xs text-ink-3">생성 중…</span>}
          </div>
          {diagnosis ? (
            <div className="text-sm leading-relaxed text-ink">
              <Markdown text={diagnosis} />
            </div>
          ) : (
            <span className="text-sm text-ink-3">실패/취약점을 분석하는 중…</span>
          )}
        </div>
      )}

      <p className="text-xs text-ink-3">
        * 제안만 하고 코드를 자동 수정하지는 않습니다 — 임계값·프롬프트 변경은 사람이 판단해 적용합니다(읽기 전용 루프).
      </p>
    </div>
  );
}
