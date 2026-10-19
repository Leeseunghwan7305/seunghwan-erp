"use client";

import { useRef, useState } from "react";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EXAMPLES = [
  "지난달 매출 상위 거래처 5개",
  "안전재고 미달 품목과 현재고",
  "월별 주문 건수",
  "미결제 매출 전표 합계",
];

interface Rows {
  columns: string[];
  rows: (string | number | null)[][];
  count: number;
}

export default function SqlPage() {
  const [q, setQ] = useState("");
  const [sql, setSql] = useState("");
  const [guard, setGuard] = useState<{ ok: boolean; reason?: string } | null>(null);
  const [rows, setRows] = useState<Rows | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const run = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setSql("");
    setGuard(null);
    setRows(null);
    setError("");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch(`${BASE}/agent/text-to-sql`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, model: "local" }),
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
            case "sql_delta":
              setSql((s) => s + evt.content);
              break;
            case "guard":
              setGuard({ ok: evt.ok, reason: evt.reason });
              if (evt.ok && evt.sql) setSql(evt.sql); // 정리된(LIMIT 부착) 최종본으로 치환
              break;
            case "rows":
              setRows({ columns: evt.columns, rows: evt.rows, count: evt.count });
              break;
            case "error":
              setError(evt.content);
              break;
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="AI · Text-to-SQL"
        title="자연어 DB 질의"
        desc="질문을 PostgreSQL SELECT로 바꿔 ERP 데이터베이스에 직접 묻습니다. 생성된 SQL을 그대로 공개하고, 읽기전용 가드(SELECT만·단일문·LIMIT·읽기전용 트랜잭션)로 안전하게 실행합니다."
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
            placeholder="예) 지난달 매출 상위 거래처 5개"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            disabled={busy}
          />
          <button
            type="submit"
            disabled={busy || !q.trim()}
            className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {busy ? "질의 중…" : "질의"}
          </button>
        </form>
        {!busy && !sql && (
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

      {sql && (
        <div className="rounded-card border border-line bg-surface p-5">
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-ink">생성된 SQL</span>
            {guard?.ok && (
              <span className="rounded-full border border-brand/40 bg-brand-tint px-2 py-0.5 text-[11px] text-brand-strong">
                ✓ 읽기전용 가드 통과
              </span>
            )}
            {guard && !guard.ok && (
              <span className="rounded-full border border-danger/40 bg-danger-tint px-2 py-0.5 text-[11px] text-danger">
                ✕ 차단: {guard.reason}
              </span>
            )}
          </div>
          <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3 font-mono text-xs leading-relaxed text-ink">
            {sql}
          </pre>
        </div>
      )}

      {error && (
        <div className="rounded-card border border-danger/40 bg-danger-tint p-4 text-sm text-danger">
          ⚠️ {error}
        </div>
      )}

      {rows && (
        <div className="rounded-card border border-line bg-surface p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="font-mono text-sm font-semibold text-ink">결과</span>
            <span className="font-mono text-xs text-ink-2">{rows.count}행</span>
          </div>
          {rows.rows.length === 0 ? (
            <span className="text-sm text-ink-3">해당하는 행이 없습니다.</span>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-ink-3">
                    {rows.columns.map((c) => (
                      <th key={c} className="py-2 pr-4 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.rows.map((r, i) => (
                    <tr key={i} className="border-b border-line/60">
                      {r.map((v, j) => (
                        <td key={j} className="py-2 pr-4 font-mono text-xs tabular-nums text-ink">
                          {v === null ? <span className="text-ink-3">—</span> : String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <p className="text-xs text-ink-3">
        * 3겹 방어: ① 프롬프트로 SELECT 유도 → ② 코드 가드(denylist·단일문·LIMIT) → ③ <code>postgresql_readonly</code> 트랜잭션 +
        <code>statement_timeout</code>. 쓰기·DDL은 DB 레벨에서 거부됩니다.
      </p>
    </div>
  );
}
