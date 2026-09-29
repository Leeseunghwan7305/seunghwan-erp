"use client";

/**
 * Generative UI — 도구 실행 결과(원자료)를 텍스트가 아니라 React 컴포넌트로 렌더한다.
 * 백엔드가 SSE로 { type:"tool_result", name, data } 를 보내면, 도구 이름에 맞는
 * 표·카드로 시각화한다. (모르는 도구/문서·웹 검색은 텍스트 답변으로 충분하므로 null)
 */

const won = (n: unknown) =>
  typeof n === "number" ? `₩${n.toLocaleString("ko-KR")}` : String(n ?? "");

type Row = Record<string, unknown>;

export default function ToolResultView({ name, data }: { name: string; data: unknown }) {
  if (name === "get_inventory" && Array.isArray(data)) return <InventoryTable rows={data} />;
  if (name === "get_dashboard" && data && typeof data === "object") return <DashboardCards d={data as Row} />;
  if (name === "list_orders" && Array.isArray(data)) return <OrdersList rows={data} />;
  if (name === "list_partners" && Array.isArray(data)) return <PartnersList rows={data} />;
  return null;
}

function Empty({ label }: { label: string }) {
  return <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs text-ink-3">{label}</div>;
}

function InventoryTable({ rows }: { rows: Row[] }) {
  if (rows.length === 0) return <Empty label="조회된 품목이 없습니다." />;
  return (
    <div className="my-1 overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-line text-ink-3">
            <th className="px-3 py-2 font-medium">코드</th>
            <th className="px-3 py-2 font-medium">품명</th>
            <th className="px-3 py-2 text-right font-medium">현재고</th>
            <th className="px-3 py-2 text-right font-medium">안전재고</th>
            <th className="px-3 py-2 text-right font-medium">판매가</th>
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {rows.map((r, i) => {
            const low = r["안전재고미달"] === true;
            return (
              <tr key={i} className={`border-b border-line/60 last:border-0 ${low ? "bg-danger-tint" : ""}`}>
                <td className="px-3 py-1.5 text-ink-2">{String(r["코드"] ?? "")}</td>
                <td className="px-3 py-1.5 font-sans text-ink">{String(r["품명"] ?? "")}</td>
                <td className={`px-3 py-1.5 text-right ${low ? "font-semibold text-danger" : "text-ink"}`}>
                  {String(r["현재재고"] ?? "")}
                  {low && <span className="ml-1 font-sans text-[10px]">미달</span>}
                </td>
                <td className="px-3 py-1.5 text-right text-ink-3">{String(r["안전재고"] ?? "")}</td>
                <td className="px-3 py-1.5 text-right text-ink-2">{won(r["판매가"])}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DashboardCards({ d }: { d: Row }) {
  const money = ["총매출", "총매입", "미수금", "미지급금"];
  const count = ["품목수", "거래처수", "총재고수량", "안전재고미달품목수", "진행중주문수"];
  const cell = (k: string, isMoney: boolean) =>
    k in d ? (
      <div key={k} className="rounded-lg border border-line bg-surface px-3 py-2">
        <div className="text-[11px] text-ink-3">{k}</div>
        <div className={`font-mono tabular-nums ${isMoney ? "text-sm" : "text-base"} font-semibold text-ink`}>
          {isMoney ? won(d[k]) : String(d[k])}
        </div>
      </div>
    ) : null;
  return (
    <div className="my-1 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
      {money.map((k) => cell(k, true))}
      {count.map((k) => cell(k, false))}
    </div>
  );
}

function OrdersList({ rows }: { rows: Row[] }) {
  if (rows.length === 0) return <Empty label="조회된 주문이 없습니다." />;
  const badge = (s: unknown) =>
    s === "confirmed" ? "border-brand text-brand-strong bg-brand-tint"
    : s === "done" ? "border-ink-2 text-ink bg-surface-2"
    : "border-line text-ink-3 bg-surface";
  return (
    <div className="my-1 flex flex-col gap-1">
      {rows.slice(0, 8).map((r, i) => (
        <div key={i} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs">
          <span className="font-mono text-ink-3">#{String(r["번호"] ?? "")}</span>
          <span className="rounded-full border border-line px-1.5 py-0.5 text-[10px] text-ink-2">{String(r["유형"] ?? "")}</span>
          <span className="flex-1 truncate text-ink">{String(r["거래처"] ?? "")}</span>
          <span className="font-mono tabular-nums text-ink-2">{won(r["합계"])}</span>
          <span className={`rounded-full border px-1.5 py-0.5 font-mono text-[10px] ${badge(r["상태"])}`}>{String(r["상태"] ?? "")}</span>
        </div>
      ))}
      {rows.length > 8 && <div className="px-1 text-[11px] text-ink-3">…외 {rows.length - 8}건</div>}
    </div>
  );
}

function PartnersList({ rows }: { rows: Row[] }) {
  if (rows.length === 0) return <Empty label="조회된 거래처가 없습니다." />;
  return (
    <div className="my-1 flex flex-col gap-1">
      {rows.slice(0, 10).map((r, i) => (
        <div key={i} className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs">
          <span className="flex-1 truncate text-ink">{String(r["이름"] ?? "")}</span>
          <span className="rounded-full border border-line px-1.5 py-0.5 text-[10px] text-ink-2">{String(r["구분"] ?? "")}</span>
          <span className="font-mono text-ink-3">{String(r["연락처"] ?? "")}</span>
        </div>
      ))}
      {rows.length > 10 && <div className="px-1 text-[11px] text-ink-3">…외 {rows.length - 10}곳</div>}
    </div>
  );
}
