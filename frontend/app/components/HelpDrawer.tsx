"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { screenHelp } from "../lib/screenHelp";
import { api, AgentProposal, RagSearchHit } from "../lib/api";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// 화면별 '실행' 예시 명령
const ACTION_EX: Record<string, string[]> = {
  품목관리: ["콜라 1.5L 코드 D-200 판매가 2000 안전재고 20으로 등록해줘", "생수 500ml 재고를 100으로 바꿔줘"],
  거래처관리: ["대박상사 공급처로 추가해줘 연락처 02-000-0000"],
  비용관리: ["오늘 광고선전비 50만원 법인카드로 등록해줘"],
  계정과목관리: ["코드 820 여비교통비 비용 차변으로 추가해줘"],
  직원관리: ["홍길동 영업부 사원으로 등록해줘"],
  "권한관리": ["뷰어 역할 만들고 대시보드만 접근 가능하게 해줘"],
};

const ACTION_LABEL: Record<string, string> = { create: "등록", update: "수정" };

export default function HelpDrawer() {
  const pathname = usePathname();
  const help = screenHelp(pathname);

  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"guide" | "manual" | "action">("guide");
  const [model, setModel] = useState<"claude" | "local">("local");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  // manual: 화면별 매뉴얼 전문(RAG에서 조회)
  const [manualText, setManualText] = useState("");
  const [manualTitle, setManualTitle] = useState<string | null>(null);
  const [manualBusy, setManualBusy] = useState(false);
  const [manualScreen, setManualScreen] = useState<string | null>(null); // 현재 로드된 화면
  const manualSeq = useRef(0); // 늦게 온 응답이 최신 화면을 덮지 않도록

  // guide
  const [asked, setAsked] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<RagSearchHit[]>([]);
  const [searching, setSearching] = useState(false);

  // action
  const [proposal, setProposal] = useState<AgentProposal | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const planSeq = useRef(0); // 늦게 도착한 옛 제안이 새 제안을 덮지 않도록

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setAsked(q); setAnswer(""); setSources([]); setBusy(true); setSearching(false); setInput("");
    // 참고 문서는 '실제 근거'만 — 유사도 임계값(0.45) 미만은 무관한 최근접이라 표시하지 않는다.
    api
      .ragSearch(q, 3)
      .then((r) => setSources((r.results ?? []).filter((h) => h.score >= 0.45)))
      .catch(() => {});
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: [{ role: "user", content: `[${help.title} 화면] ${q}` }],
          doc_min_score: 0.35,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`서버 오류 (${res.status})`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n"); buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const evt = JSON.parse(line.slice(5).trim());
          if (evt.type === "tool") setSearching(true);
          else if (evt.type === "text") setAnswer((a) => a + evt.content);
          else if (evt.type === "error") setAnswer((a) => a + `⚠️ ${evt.content}`);
        }
      }
    } catch (e) {
      setAnswer(`⚠️ ${(e as Error).message}`);
    } finally {
      setBusy(false); setSearching(false);
    }
  };

  const planAction = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    const seq = ++planSeq.current;
    setProposal(null); setApplied(null); setBusy(true); setInput("");
    try {
      const p = await api.agentPlan(q, help.title);
      if (seq !== planSeq.current) return; // 더 최근 요청이 있으면 이 응답은 버림
      setProposal(p);
    } catch (e) {
      if (seq === planSeq.current) setProposal({ ok: false, error: (e as Error).message });
    } finally {
      if (seq === planSeq.current) setBusy(false);
    }
  };

  const applyProposal = async () => {
    if (!proposal || busy) return;
    setBusy(true);
    try {
      const r = await api.agentApply(proposal);
      if (r.ok) {
        setApplied(r.message ?? "적용되었습니다.");
        setProposal(null);
        // 목록 화면이 자동 새로고침하도록 알림
        window.dispatchEvent(new CustomEvent("erp:data-changed"));
      } else {
        setApplied(`⚠️ ${r.error ?? "적용 실패"}`);
      }
    } catch (e) {
      setApplied(`⚠️ ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const loadManual = async () => {
    const seq = ++manualSeq.current;
    setManualBusy(true); setManualText(""); setManualTitle(null);
    try {
      const r = await api.ragManual(help.manual ?? help.title, help.manualSection);
      if (seq !== manualSeq.current) return; // 화면이 바뀌었으면 버림
      setManualText(r.text || ""); setManualTitle(r.title); setManualScreen(help.title);
    } catch (e) {
      if (seq === manualSeq.current) { setManualText(`⚠️ ${(e as Error).message}`); setManualScreen(help.title); }
    } finally {
      if (seq === manualSeq.current) setManualBusy(false);
    }
  };

  // 매뉴얼 탭이 열려 있고 아직 이 화면 매뉴얼을 안 불렀으면 조회.
  useEffect(() => {
    if (open && mode === "manual" && manualScreen !== help.title && !manualBusy) loadManual();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode, help.title]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    mode === "guide" ? ask(input) : planAction(input);
  };

  const examples = mode === "guide" ? help.questions : (ACTION_EX[help.title] ?? []);

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-brand px-4 py-3 text-sm font-medium text-white shadow-lg transition-colors hover:bg-brand-strong"
          aria-label="도움말 열기"
        >
          <span className="text-base leading-none">?</span> 도움말
        </button>
      )}

      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-ink/20" onClick={() => setOpen(false)} />
          <aside className="fixed inset-y-0 right-0 z-50 flex w-[400px] max-w-[92vw] flex-col border-l border-line bg-surface shadow-xl">
            <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
              <div className="leading-tight">
                <div className="eyebrow">도움말 · {mode === "guide" ? "안내" : mode === "manual" ? "매뉴얼" : "실행"}</div>
                <div className="text-[15px] font-semibold text-ink">{help.title}</div>
              </div>
              <button onClick={() => setOpen(false)} className="text-ink-3 transition-colors hover:text-ink" aria-label="닫기">✕</button>
            </div>

            {/* 모드 토글 */}
            <div className="flex gap-1 border-b border-line px-5 py-2.5">
              {(["guide", "manual", "action"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    mode === m ? "bg-brand text-white" : "text-ink-2 hover:bg-surface-2"
                  }`}
                >
                  {m === "guide" ? "🔎 안내(읽기)" : m === "manual" ? "📖 매뉴얼" : "⚡ 실행(쓰기)"}
                </button>
              ))}
            </div>

            {/* 답변 모델 선택 (안내 모드) */}
            {mode === "guide" && (
              <div className="flex items-center gap-2 border-b border-line px-5 py-2">
                <span className="text-[11px] text-ink-3">답변 모델</span>
                <div className="inline-flex overflow-hidden rounded-md border border-line text-xs">
                  {(["claude", "local"] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setModel(m)}
                      disabled={busy}
                      className={`px-3 py-1 transition-colors disabled:opacity-50 ${
                        model === m ? "bg-brand text-white" : "bg-surface text-ink-2 hover:text-ink"
                      }`}
                    >
                      {m === "claude" ? "Claude" : "로컬 LLM"}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex-1 overflow-y-auto px-5 py-4">
              {/* 예시 (안내·실행 모드) */}
              {mode !== "manual" && (
                <>
                  <div className="mb-2 text-xs font-medium text-ink-2">
                    {mode === "guide" ? "자주 묻는 질문" : "예시 명령"}
                  </div>
                  <div className="mb-5 flex flex-wrap gap-2">
                    {examples.map((q) => (
                      <button
                        key={q}
                        onClick={() => (mode === "guide" ? ask(q) : planAction(q))}
                        disabled={busy}
                        className="rounded-full border border-line-strong px-3 py-1.5 text-left text-xs text-ink transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
                      >
                        {q}
                      </button>
                    ))}
                    {examples.length === 0 && (
                      <span className="text-xs text-ink-3">이 화면에서 실행할 작업을 아래에 입력하세요.</span>
                    )}
                  </div>
                </>
              )}

              {/* MANUAL 결과 — 화면별 매뉴얼 전문 */}
              {mode === "manual" && (
                <div>
                  {manualBusy && !manualText && (
                    <div className="text-xs text-ink-3">📖 매뉴얼 불러오는 중…</div>
                  )}
                  {!manualBusy && !manualText && (
                    <div className="text-xs text-ink-3">이 화면의 매뉴얼을 찾지 못했습니다.</div>
                  )}
                  {manualText && (
                    <>
                      <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink-2">
                        {manualText}
                      </div>
                      {manualTitle && (
                        <div className="mt-4 border-t border-line pt-3">
                          <span className="rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[11px] text-ink-2">
                            📄 {manualTitle}
                          </span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* GUIDE 결과 */}
              {mode === "guide" && asked && (
                <div className="space-y-2 border-t border-line pt-4">
                  <div className="text-sm font-medium text-ink">Q. {asked}</div>
                  {searching && !answer && <div className="text-xs text-ink-3">🔎 지식 문서 검색 중…</div>}
                  {!answer && !searching && busy && <div className="text-xs text-ink-3">답변 생성 중…</div>}
                  {answer && <div className="whitespace-pre-wrap text-sm leading-relaxed text-ink-2">{answer}</div>}
                  {sources.length > 0 && (
                    <div className="pt-2">
                      <div className="mb-1 text-[11px] font-medium text-ink-3">참고 문서</div>
                      <div className="flex flex-wrap gap-1.5">
                        {Array.from(new Set(sources.map((s) => s.title))).map((t) => (
                          <span key={t} className="rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[11px] text-ink-2">📄 {t}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ACTION 결과 */}
              {mode === "action" && busy && !proposal && (
                <div className="text-xs text-ink-3">제안 생성 중…</div>
              )}
              {mode === "action" && applied && (
                <div className="rounded-md border border-brand/30 bg-brand-tint px-3 py-2.5 text-sm text-brand-strong">
                  ✓ {applied}
                </div>
              )}
              {mode === "action" && proposal && (
                <div className="border-t border-line pt-4">
                  {proposal.ok ? (
                    <div className="rounded-card border border-line bg-surface-2 p-4">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="rounded-full bg-brand px-2 py-0.5 text-[11px] font-medium text-white">
                          {proposal.entity_label} {ACTION_LABEL[proposal.action ?? ""] ?? proposal.action}
                        </span>
                      </div>
                      <p className="mb-3 text-sm text-ink">{proposal.summary}</p>
                      <table className="w-full text-[13px]">
                        <tbody>
                          {Object.entries(proposal.values ?? {}).map(([k, v]) => (
                            <tr key={k} className="border-b border-line last:border-0">
                              <td className="py-1.5 pr-3 font-mono text-[11px] uppercase tracking-wide text-ink-3 align-top">{k}</td>
                              <td className="py-1.5 text-ink">{String(v)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {proposal.target?.code && (
                        <p className="mt-2 text-[11px] text-ink-3">대상: {proposal.target.code}</p>
                      )}
                      {proposal.warnings && proposal.warnings.length > 0 && (
                        <ul className="mt-3 space-y-1">
                          {proposal.warnings.map((w, i) => (
                            <li key={i} className="text-[12px] text-freight">⚠ {w}</li>
                          ))}
                        </ul>
                      )}
                      <div className="mt-4 flex justify-end gap-2">
                        <button onClick={() => setProposal(null)} disabled={busy}
                          className="rounded-md border border-line-strong px-3 py-1.5 text-sm text-ink-2 hover:bg-surface disabled:opacity-50">취소</button>
                        <button onClick={applyProposal} disabled={busy}
                          className="rounded-md bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-strong disabled:opacity-50">
                          {busy ? "적용 중…" : "적용"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-md border border-danger/30 bg-danger-tint px-3 py-2.5 text-sm text-danger">
                      ⚠️ {proposal.error ?? "제안을 만들지 못했습니다."}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 입력 (매뉴얼 모드는 읽기 전용이라 숨김) */}
            {mode !== "manual" && (
            <form onSubmit={submit} className="flex gap-2 border-t border-line p-4">
              <input
                className="min-w-0 flex-1 rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
                placeholder={mode === "guide" ? "이 화면에 대해 물어보세요" : "실행할 작업을 말하세요 (예: OO 등록해줘)"}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={busy}
              />
              <button type="submit" disabled={busy || !input.trim()}
                className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50">
                {mode === "guide" ? "질문" : "제안"}
              </button>
            </form>
            )}
          </aside>
        </>
      )}
    </>
  );
}
