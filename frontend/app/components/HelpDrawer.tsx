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

// 도구 → '출처 카테고리'. 답변이 실제로 무엇을 근거로 했는지 배지로 보여줘 오해를 없앤다.
const SOURCE: Record<string, { label: string; cls: string }> = {
  web_search: { label: "🌐 웹 검색", cls: "border-freight text-freight bg-freight-tint" },
  search_documents: { label: "📄 사내 문서", cls: "border-brand text-brand-strong bg-brand-tint" },
  doc_context: { label: "📄 사내 문서", cls: "border-brand text-brand-strong bg-brand-tint" },
};
// 문서 근거 도구(이게 실제로 호출됐을 때만 '참고 문서'를 노출한다)
const DOC_TOOLS = new Set(["doc_context", "search_documents"]);

function sourceBadges(tools: string[]): { label: string; cls: string }[] {
  const seen = new Set<string>();
  const out: { label: string; cls: string }[] = [];
  for (const t of tools) {
    const s = SOURCE[t] ?? { label: "📊 ERP 데이터", cls: "border-ink-2 text-ink bg-surface-2" };
    if (!seen.has(s.label)) {
      seen.add(s.label);
      out.push(s);
    }
  }
  return out;
}

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
  const [usedTools, setUsedTools] = useState<string[]>([]); // 이 답변이 실제 호출한 도구(=출처)
  const [searching, setSearching] = useState(false);

  // action
  const [proposal, setProposal] = useState<AgentProposal | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const planSeq = useRef(0); // 늦게 도착한 옛 제안이 새 제안을 덮지 않도록

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setAsked(q); setAnswer(""); setSources([]); setUsedTools([]); setBusy(true); setSearching(false); setInput("");
    // 참고 문서는 '실제 근거'만 노출한다. 답변과 무관하게 최근접 문서를 미리 뽑아 보여주면
    // 웹검색으로 답했는데도 사내 문서가 딸려 나와 마치 근거처럼 오해된다(할루시네이션처럼 보임).
    // 그래서 스트림에서 '문서 도구'가 실제 호출됐을 때만 아래에서 제목을 가져온다.
    const used = new Set<string>();
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: [{ role: "user", content: `[${help.title} 화면] ${q}` }],
          // 임계값은 백엔드 기본(0.50)을 쓴다. 예전엔 0.35로 낮췄으나, 무관한 질문에도
          // 사내 문서가 주입돼 오답 근거가 붙는 부작용이 커서 제거함.
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
          if (evt.type === "tool") {
            used.add(evt.name);
            setUsedTools([...used]);
            setSearching(true);
          } else if (evt.type === "text") setAnswer((a) => a + evt.content);
          else if (evt.type === "error") setAnswer((a) => a + `⚠️ ${evt.content}`);
        }
      }
      // 답변이 '실제로' 사내 문서를 근거로 했을 때만 제목을 가져와 표시한다.
      const usedDoc = [...used].some((t) => DOC_TOOLS.has(t));
      if (usedDoc) {
        try {
          const r = await api.ragSearch(q, 3);
          // 자동 주입 임계값(0.50)과 동일하게 걸러 실제 근거가 된 문서만 노출한다.
          setSources((r.results ?? []).filter((h) => h.score >= 0.5));
        } catch {
          /* 제목 조회 실패는 무시 — 답변 자체는 이미 표시됨 */
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
                  {answer && !answer.startsWith("⚠️") && (
                    <div className="flex flex-wrap items-center gap-1">
                      <span className="mr-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-3">근거</span>
                      {usedTools.length > 0 ? (
                        sourceBadges(usedTools).map((s, j) => (
                          <span key={j} className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${s.cls}`}>
                            {s.label}
                          </span>
                        ))
                      ) : (
                        !answer.includes("찾을 수 없습니다") && (
                          <span className="rounded-full border border-danger/40 bg-danger-tint px-2 py-0.5 font-mono text-[11px] text-danger">
                            🧠 모델 지식(근거 없음)
                          </span>
                        )
                      )}
                    </div>
                  )}
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
