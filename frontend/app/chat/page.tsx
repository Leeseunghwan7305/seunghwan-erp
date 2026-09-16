"use client";

import { useRef, useState } from "react";
import PageHeader from "../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Role = "user" | "assistant";
interface Msg {
  role: Role;
  content: string;
  tools?: string[]; // 이 답변을 만들며 호출한 도구 이름들
}

const TOOL_LABEL: Record<string, string> = {
  get_dashboard: "현황 요약 조회",
  get_inventory: "재고 조회",
  list_orders: "주문 조회",
  list_partners: "거래처 조회",
  search_documents: "지식 문서 검색",
};

const SUGGESTIONS = [
  "탄산수 재고 얼마나 있어?",
  "안전재고 미달인 품목 알려줘",
  "이번 현황 요약해줘 (매출·미수금 포함)",
  "확정된 발주 주문 보여줘",
];

export default function ChatPage() {
  const [model, setModel] = useState<"claude" | "local">("claude");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollDown = () =>
    requestAnimationFrame(() =>
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
    );

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    const history: Msg[] = [...messages, { role: "user", content: text }];
    setMessages([...history, { role: "assistant", content: "", tools: [] }]);
    setInput("");
    setBusy(true);
    scrollDown();

    const patchLast = (fn: (m: Msg) => Msg) =>
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = fn(copy[copy.length - 1]);
        return copy;
      });

    try {
      const res = await fetch(`${BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: history.map((m) => ({ role: m.role, content: m.content })),
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
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const evt = JSON.parse(line.slice(5).trim());
          if (evt.type === "tool") {
            patchLast((m) => ({
              ...m,
              tools: [...(m.tools ?? []), TOOL_LABEL[evt.name] ?? evt.name],
            }));
          } else if (evt.type === "text") {
            patchLast((m) => ({ ...m, content: m.content + evt.content }));
          } else if (evt.type === "error") {
            patchLast((m) => ({ ...m, content: `⚠️ ${evt.content}` }));
          }
          scrollDown();
        }
      }
    } catch (e) {
      patchLast((m) => ({ ...m, content: `⚠️ ${(e as Error).message}` }));
    } finally {
      setBusy(false);
      scrollDown();
    }
  };

  return (
    <div className="flex h-[calc(100vh-4.5rem)] flex-col">
      <PageHeader
        eyebrow="Assistant"
        title="AI 어시스턴트"
        desc="재고·주문·정산을 물어보면 실제 데이터를 조회해 답합니다. (조회 전용)"
        meta={
          <div className="inline-flex overflow-hidden rounded-md border border-line text-sm">
            {(["claude", "local"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setModel(m)}
                className={`px-4 py-1.5 transition-colors ${
                  model === m
                    ? "bg-brand text-white"
                    : "bg-surface text-ink-2 hover:text-ink"
                }`}
              >
                {m === "claude" ? "Claude" : "로컬 LLM"}
              </button>
            ))}
          </div>
        }
      />

      {/* 메시지 영역 */}
      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto rounded-card border border-line bg-surface p-5"
      >
        {messages.length === 0 && (
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
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === "user"
                  ? "rounded-br-sm bg-brand text-white"
                  : "rounded-bl-sm border border-line bg-surface-2 text-ink"
              }`}
            >
              {m.tools && m.tools.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {m.tools.map((t, j) => (
                    <span
                      key={j}
                      className="rounded-full border border-line bg-surface px-2 py-0.5 font-mono text-[11px] text-ink-2"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
              {m.content ||
                (m.role === "assistant" && busy ? (
                  <span className="text-ink-3">생각 중…</span>
                ) : (
                  ""
                ))}
            </div>
          </div>
        ))}
      </div>

      {/* 입력 */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-4 flex gap-2"
      >
        <input
          className="flex-1 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
          placeholder="예) 안전재고 미달 품목 알려줘"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
        >
          전송
        </button>
      </form>
    </div>
  );
}
