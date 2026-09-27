"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import PageHeader from "../components/PageHeader";
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  saveConversation,
  type Msg,
} from "../lib/conversations";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// 6단계 코드 스플리팅: Markdown 렌더러를 별도 청크로 지연 로드.
const Markdown = dynamic(() => import("../components/Markdown"), { ssr: false });

// 도구 → '출처 카테고리'. 색으로 구분해 근거를 명확히.
const SOURCE: Record<string, { label: string; cls: string }> = {
  web_search: { label: "🌐 웹 검색", cls: "border-freight text-freight bg-freight-tint" },
  search_documents: { label: "📄 사내 문서", cls: "border-brand text-brand-strong bg-brand-tint" },
  doc_context: { label: "📄 사내 문서", cls: "border-brand text-brand-strong bg-brand-tint" },
  get_dashboard: { label: "📊 ERP 데이터", cls: "border-ink-2 text-ink bg-surface-2" },
  get_inventory: { label: "📊 ERP 데이터", cls: "border-ink-2 text-ink bg-surface-2" },
  list_orders: { label: "📊 ERP 데이터", cls: "border-ink-2 text-ink bg-surface-2" },
  list_partners: { label: "📊 ERP 데이터", cls: "border-ink-2 text-ink bg-surface-2" },
};

function sourceBadges(tools: string[] | undefined): { label: string; cls: string }[] {
  const seen = new Set<string>();
  const out: { label: string; cls: string }[] = [];
  for (const t of tools ?? []) {
    const s = SOURCE[t] ?? { label: t, cls: "border-line text-ink-2 bg-surface" };
    if (!seen.has(s.label)) {
      seen.add(s.label);
      out.push(s);
    }
  }
  return out;
}

const SUGGESTIONS = [
  "탄산수 재고 얼마나 있어?",
  "안전재고 미달인 품목 알려줘",
  "이번 현황 요약해줘 (매출·미수금 포함)",
  "확정된 발주 주문 보여줘",
];

// 5단계 Reconnect: 네트워크 오류 시 1회 재연결(중단은 그대로 전파).
async function fetchWithReconnect(
  url: string,
  opts: RequestInit,
  onRetry?: () => void
): Promise<Response> {
  try {
    return await fetch(url, opts);
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    onRetry?.();
    await new Promise((r) => setTimeout(r, 800));
    return await fetch(url, opts);
  }
}

function ChatInner() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const cid = params.get("c");

  // 2단계: 대화 목록은 TanStack Query로 캐시·무효화.
  const { data: conversations = [] } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });

  const [messages, setMessages] = useState<Msg[]>([]);
  const [model, setModel] = useState<"claude" | "local">("claude");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showJump, setShowJump] = useState(false); // '↓ 최신으로' 버튼 노출
  const [toast, setToast] = useState<string | null>(null); // 비침습 알림
  const abortRef = useRef<AbortController | null>(null);
  const messagesRef = useRef<Msg[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const stick = useRef(true); // 하단 고정(자동 스크롤) 여부
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 1800);
  };

  // 입력창 자동 높이(내용에 맞춰 늘고 최대 높이에서 스크롤).
  const autoGrow = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const setMsgs = (updater: Msg[] | ((p: Msg[]) => Msg[])) =>
    setMessages((prev) => {
      const next = typeof updater === "function" ? (updater as (p: Msg[]) => Msg[])(prev) : updater;
      messagesRef.current = next;
      return next;
    });

  // URL에 대화 id가 없으면 최근 대화(또는 새 대화)로 이동해 항상 딥링크 가능.
  useEffect(() => {
    if (cid) return;
    const list = listConversations();
    const target = list[0]?.id ?? createConversation().id;
    qc.invalidateQueries({ queryKey: ["conversations"] });
    router.replace(`/chat?c=${target}`);
  }, [cid, router, qc]);

  // 현재 대화 로드(스트리밍 중이 아닐 때만 덮어씀).
  useEffect(() => {
    if (!cid) return;
    const conv = getConversation(cid);
    const msgs = conv?.messages ?? [];
    messagesRef.current = msgs;
    setMessages(msgs);
    setModel(conv?.model ?? "claude");
    stick.current = true;
    requestAnimationFrame(scrollToBottom);
  }, [cid]);

  const persist = (msgs: Msg[], mdl = model) => {
    if (!cid) return;
    saveConversation(cid, { messages: msgs, model: mdl });
    qc.invalidateQueries({ queryKey: ["conversations"] });
  };

  // 6단계: 메시지 리스트 가상화(가변 높이, 동적 측정).
  const rowVirtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 96,
    overscan: 8,
    measureElement: (el) => el.getBoundingClientRect().height,
  });

  const scrollToBottom = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  const jumpToBottom = () => {
    stick.current = true;
    setShowJump(false);
    requestAnimationFrame(scrollToBottom);
  };

  // 스트리밍 중 하단 고정: 사용자가 위로 스크롤하면 고정 해제하고 '↓ 최신으로' 노출.
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    stick.current = atBottom;
    setShowJump(!atBottom && messages.length > 0);
  };

  useEffect(() => {
    if (stick.current) requestAnimationFrame(scrollToBottom);
  }, [messages]);

  // 입력 내용이 바뀌면(전송 후 비워짐 포함) 입력창 높이 재계산.
  useEffect(() => {
    autoGrow();
  }, [input]);

  const clearCurrent = () => {
    if (busy || !cid) return;
    setMsgs([]);
    persist([]);
  };

  const newChat = () => {
    if (busy) return;
    const conv = createConversation(model);
    qc.invalidateQueries({ queryKey: ["conversations"] });
    setMenuOpen(false);
    router.push(`/chat?c=${conv.id}`);
  };

  const selectChat = (id: string) => {
    if (busy) return;
    setMenuOpen(false);
    router.push(`/chat?c=${id}`);
  };

  const removeChat = (id: string) => {
    if (busy) return;
    deleteConversation(id);
    qc.invalidateQueries({ queryKey: ["conversations"] });
    if (id === cid) router.replace("/chat");
  };

  const sendToSlack = async (text: string) => {
    if (!text.trim() || text.startsWith("⚠️")) return;
    if (!window.confirm(`이 내용을 슬랙으로 보낼까요?\n\n${text.slice(0, 300)}`)) return;
    let actor: string | undefined;
    try {
      actor = JSON.parse(localStorage.getItem("erp_current_user") || "{}").name;
    } catch {
      /* ignore */
    }
    try {
      const res = await fetch(`${BASE}/integrations/slack/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, actor }),
      });
      const r = await res.json();
      showToast(r.ok ? "✅ 슬랙으로 전송했습니다." : `⚠️ ${r.error}`);
    } catch (e) {
      showToast(`⚠️ ${(e as Error).message}`);
    }
  };

  // 답변 복사(클립보드 미지원 환경 폴백 포함).
  const copyText = async (text: string) => {
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
      else {
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      }
      showToast("복사되었습니다");
    } catch {
      showToast("⚠️ 복사 실패");
    }
  };

  const stop = () => abortRef.current?.abort();

  const retry = () => {
    if (busy) return;
    let end = messages.length;
    while (end > 0 && messages[end - 1].role === "assistant") end--;
    const history = messages.slice(0, end);
    if (history.length === 0) return;
    runStream(history);
  };

  const send = (text: string) => {
    if (!text.trim() || busy) return;
    setInput("");
    runStream([...messages, { role: "user", content: text }]);
  };

  const runStream = async (history: Msg[]) => {
    setMsgs([...history, { role: "assistant", content: "", tools: [] }]);
    setBusy(true);
    stick.current = true;
    requestAnimationFrame(scrollToBottom);

    const controller = new AbortController();
    abortRef.current = controller;

    const patchLast = (fn: (m: Msg) => Msg) =>
      setMsgs((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = fn(copy[copy.length - 1]);
        return copy;
      });

    try {
      const res = await fetchWithReconnect(
        `${BASE}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model,
            messages: history.map((m) => ({ role: m.role, content: m.content })),
          }),
          signal: controller.signal,
        },
        () => patchLast((m) => ({ ...m, content: m.content })) // 재연결 시도(조용히 1회)
      );
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
            patchLast((m) => ({ ...m, tools: [...(m.tools ?? []), evt.name] }));
          } else if (evt.type === "text") {
            patchLast((m) => ({ ...m, content: m.content + evt.content }));
          } else if (evt.type === "error") {
            patchLast((m) => ({ ...m, content: `⚠️ ${evt.content}` }));
          }
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        patchLast((m) => ({ ...m, content: m.content || "(중단됨)" }));
      } else {
        patchLast((m) => ({ ...m, content: `⚠️ ${(e as Error).message}` }));
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
      persist(messagesRef.current); // 2단계: 완료 후 현재 대화에 저장
      requestAnimationFrame(scrollToBottom);
    }
  };

  const current = conversations.find((c) => c.id === cid);

  const renderBubble = (m: Msg, i: number) => (
    <div className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} py-2`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          m.role === "user"
            ? "rounded-br-sm bg-brand text-white"
            : "rounded-bl-sm border border-line bg-surface-2 text-ink"
        }`}
      >
        {m.role === "assistant" && (m.content || (m.tools && m.tools.length > 0)) && (
          <div className="mb-2 flex flex-wrap items-center gap-1">
            <span className="mr-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-3">근거</span>
            {sourceBadges(m.tools).map((s, j) => (
              <span key={j} className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${s.cls}`}>
                {s.label}
              </span>
            ))}
            {(!m.tools || m.tools.length === 0) &&
              m.content &&
              !m.content.startsWith("⚠️") &&
              !m.content.includes("찾을 수 없습니다") && (
                <span className="rounded-full border border-danger/40 bg-danger-tint px-2 py-0.5 font-mono text-[11px] text-danger">
                  🧠 모델 지식(근거 없음)
                </span>
              )}
          </div>
        )}
        {m.role === "assistant" && m.content && !m.content.startsWith("⚠️") ? (
          <Markdown text={m.content} />
        ) : m.content ? (
          <span className="whitespace-pre-wrap">{m.content}</span>
        ) : m.role === "assistant" && busy && i === messages.length - 1 ? (
          m.tools && m.tools.length > 0 ? (
            <span className="inline-flex items-center gap-2 text-[13px] text-ink-2">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-line border-t-brand" />
              🔧 {sourceBadges(m.tools).map((s) => s.label).join(" · ")} 실행 중…
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-ink-3">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3 [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3 [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3" />
            </span>
          )
        ) : null}
        {m.role === "assistant" && m.content && !m.content.startsWith("⚠️") && !busy && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-line pt-2">
            <button
              onClick={() => copyText(m.content)}
              className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-[11px] text-ink-2 transition-colors hover:border-brand hover:text-brand"
            >
              ⧉ 복사
            </button>
            {i === messages.length - 1 && (
              <button
                onClick={retry}
                className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-[11px] text-ink-2 transition-colors hover:border-brand hover:text-brand"
              >
                ↻ 다시 생성
              </button>
            )}
            <button
              onClick={() => sendToSlack(m.content)}
              className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-[11px] text-ink-2 transition-colors hover:border-brand hover:text-brand"
            >
              ↗ 슬랙으로 보내기
            </button>
          </div>
        )}
        {m.role === "assistant" && m.content.startsWith("⚠️") && !busy && i === messages.length - 1 && (
          <div className="mt-2 border-t border-danger/20 pt-2">
            <button
              onClick={retry}
              className="rounded-md border border-danger/40 bg-danger-tint px-2 py-1 font-mono text-[11px] text-danger transition-colors hover:bg-danger/10"
            >
              ↺ 다시 시도
            </button>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-[calc(100vh-4.5rem)] flex-col">
      <PageHeader
        eyebrow="Assistant"
        title="AI 어시스턴트"
        desc="재고·주문·정산을 물어보면 실제 데이터를 조회해 답합니다. (조회 전용)"
        meta={
          <div className="flex items-center gap-2">
            {/* 2단계: 대화 목록 스위처 */}
            <div className="relative">
              <button
                onClick={() => setMenuOpen((o) => !o)}
                disabled={busy}
                className="flex max-w-[180px] items-center gap-1 rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
              >
                <span className="truncate">{current?.title ?? "대화"}</span>
                <span className="text-ink-3">▾</span>
              </button>
              {menuOpen && (
                <div className="absolute right-0 z-20 mt-1 max-h-80 w-72 overflow-y-auto rounded-lg border border-line bg-surface p-1 shadow-lg">
                  <button
                    onClick={newChat}
                    className="mb-1 w-full rounded-md px-3 py-2 text-left text-sm text-brand hover:bg-brand-tint"
                  >
                    ＋ 새 대화
                  </button>
                  {conversations.length === 0 && (
                    <p className="px-3 py-2 text-xs text-ink-3">대화가 없습니다.</p>
                  )}
                  {conversations.map((c) => (
                    <div
                      key={c.id}
                      className={`group flex items-center gap-1 rounded-md px-2 ${
                        c.id === cid ? "bg-surface-2" : "hover:bg-surface-2"
                      }`}
                    >
                      <button
                        onClick={() => selectChat(c.id)}
                        className="flex-1 truncate py-2 text-left text-sm text-ink"
                      >
                        {c.title}
                      </button>
                      <button
                        onClick={() => removeChat(c.id)}
                        className="px-1 text-ink-3 opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
                        title="삭제"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {messages.length > 0 && (
              <button
                onClick={clearCurrent}
                disabled={busy}
                className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
              >
                비우기
              </button>
            )}
            <div className="inline-flex overflow-hidden rounded-md border border-line text-sm">
              {(["claude", "local"] as const).map((mm) => (
                <button
                  key={mm}
                  onClick={() => {
                    setModel(mm);
                    persist(messagesRef.current, mm);
                  }}
                  className={`px-4 py-1.5 transition-colors ${
                    model === mm ? "bg-brand text-white" : "bg-surface text-ink-2 hover:text-ink"
                  }`}
                >
                  {mm === "claude" ? "Claude" : "로컬 LLM"}
                </button>
              ))}
            </div>
          </div>
        }
      />

      {/* 메시지 영역 (가상화) */}
      <div className="relative min-h-0 flex-1">
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="h-full overflow-y-auto rounded-card border border-line bg-surface p-5"
      >
        {messages.length === 0 ? (
          <div>
            <p className="eyebrow mb-3">예시 질문</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative", width: "100%" }}>
            {rowVirtualizer.getVirtualItems().map((vi) => (
              <div
                key={vi.key}
                data-index={vi.index}
                ref={rowVirtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${vi.start}px)`,
                }}
              >
                {renderBubble(messages[vi.index], vi.index)}
              </div>
            ))}
          </div>
        )}
      </div>
        {showJump && (
          <button
            onClick={jumpToBottom}
            className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-line bg-surface px-3 py-1.5 text-xs text-ink-2 shadow-md transition-colors hover:border-brand hover:text-brand"
          >
            ↓ 최신으로
          </button>
        )}
        {toast && (
          <div className="absolute bottom-4 right-4 rounded-lg bg-brand-strong px-3 py-2 text-xs font-medium text-white shadow-lg">
            {toast}
          </div>
        )}
      </div>

      {/* 입력 */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-4 flex items-end gap-2"
      >
        <textarea
          ref={inputRef}
          rows={1}
          className="max-h-40 flex-1 resize-none rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
          placeholder="예) 안전재고 미달 품목 알려줘  (Shift+Enter 줄바꿈)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            } else if (e.key === "Escape" && busy) {
              e.preventDefault();
              stop();
            }
          }}
        />
        {busy ? (
          <button
            type="button"
            onClick={stop}
            className="inline-flex items-center gap-2 rounded-lg border border-danger/50 bg-danger-tint px-6 py-3 text-sm font-medium text-danger transition-colors hover:bg-danger/10"
          >
            <span className="h-2.5 w-2.5 rounded-[2px] bg-danger" />
            중지
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            전송
          </button>
        )}
      </form>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="p-5 text-sm text-ink-3">불러오는 중…</div>}>
      <ChatInner />
    </Suspense>
  );
}
