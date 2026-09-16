"use client";

import { useEffect, useState } from "react";
import PageHeader from "../../components/PageHeader";
import DataTable, { Column } from "../../components/DataTable";
import Badge from "../../components/Badge";
import Modal from "../../components/Modal";
import { api, Item, Order, Partner, statusLabel, won } from "../../lib/api";

const columns: Column[] = [
  { key: "no", label: "수주번호" },
  { key: "date", label: "수주일" },
  { key: "customer", label: "거래처" },
  { key: "item", label: "주요품목" },
  { key: "amount", label: "금액", align: "right" },
  { key: "status", label: "상태", align: "center" },
  { key: "act", label: "관리", align: "right" },
];

const statusTone = (s: Order["status"]) =>
  s === "done" ? "green" : s === "confirmed" ? "blue" : "amber";

const inputCls =
  "w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none";
const btnPrimary =
  "rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50";
const btnGhost =
  "rounded-md border border-line-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:bg-surface-2";

type Line = { item_id: number; quantity: number };

export default function SalesOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [open, setOpen] = useState(false);
  const [partnerId, setPartnerId] = useState<number | "">("");
  const [lines, setLines] = useState<Line[]>([{ item_id: 0, quantity: 1 }]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([api.orders(), api.partners(), api.items()])
      .then(([o, p, i]) => {
        setOrders(o.filter((x) => x.order_type === "sale"));
        setPartners(p.filter((x) => x.kind === "customer"));
        setItems(i);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const openCreate = () => {
    setPartnerId(partners[0]?.id ?? "");
    setLines([{ item_id: items[0]?.id ?? 0, quantity: 1 }]);
    setOpen(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!partnerId) return alert("거래처를 선택하세요.");
    const valid = lines.filter((l) => l.item_id && l.quantity > 0);
    if (!valid.length) return alert("품목을 최소 1개 추가하세요.");
    setBusy(true);
    try {
      await api.createOrder({ order_type: "sale", partner_id: Number(partnerId), lines: valid });
      setOpen(false);
      load();
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (id: number) => {
    try {
      await api.confirmOrder(id);
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };
  const remove = async (id: number) => {
    if (!confirm2("이 수주를 삭제하시겠습니까?")) return;
    try {
      await api.deleteOrder(id);
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };
  // window.confirm 래퍼 (이름 충돌 방지)
  function confirm2(m: string) {
    return window.confirm(m);
  }

  const total = orders.reduce((a, o) => a + o.total, 0);

  const rows: Record<string, React.ReactNode>[] = orders.map((o) => ({
    no: <span className="num text-ink-3">SO-{String(o.id).padStart(4, "0")}</span>,
    date: <span className="num text-ink-2">{o.order_date}</span>,
    customer: <span className="font-medium">{o.partner_name}</span>,
    item: o.lines[0]
      ? `${o.lines[0].item_name}${o.lines.length > 1 ? ` 외 ${o.lines.length - 1}건` : ""}`
      : "-",
    amount: won(o.total),
    status: <Badge tone={statusTone(o.status)}>{statusLabel[o.status]}</Badge>,
    act: (
      <div className="flex justify-end gap-1.5">
        {o.status === "draft" && (
          <button
            onClick={() => confirm(o.id)}
            className="rounded border border-line-strong px-2 py-1 text-xs text-brand transition-colors hover:bg-brand-tint"
          >
            확정
          </button>
        )}
        {o.status === "draft" && (
          <button
            onClick={() => remove(o.id)}
            className="rounded border border-line-strong px-2 py-1 text-xs text-danger transition-colors hover:bg-danger-tint"
          >
            삭제
          </button>
        )}
        {o.status !== "draft" && <span className="text-xs text-ink-3">—</span>}
      </div>
    ),
  }));

  const setLine = (i: number, patch: Partial<Line>) =>
    setLines((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  return (
    <div>
      <PageHeader
        eyebrow="Sales · Orders"
        title="수주현황"
        desc="고객 수주(판매 주문) — 등록 후 '확정'하면 재고·전표에 반영됩니다."
        meta={
          <>
            총 <span className="num text-ink">{orders.length}</span>건 · 합계{" "}
            <span className="num text-ink">{won(total)}</span>
          </>
        }
      />

      <div className="mb-3 flex justify-end">
        <button onClick={openCreate} className={btnPrimary} disabled={loading}>
          + 수주 등록
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-card border border-danger/30 bg-danger-tint px-4 py-3 text-sm text-danger">
          오류: {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ink-2">불러오는 중…</p>
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="수주 등록">
        <form onSubmit={submit} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-ink-2">거래처(고객) *</span>
            <select
              className={inputCls}
              value={partnerId}
              onChange={(e) => setPartnerId(Number(e.target.value))}
              required
            >
              {partners.length === 0 && <option value="">고객 거래처가 없습니다</option>}
              {partners.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-medium text-ink-2">품목</span>
              <button
                type="button"
                onClick={() => setLines((ls) => [...ls, { item_id: items[0]?.id ?? 0, quantity: 1 }])}
                className="text-xs text-brand hover:underline"
              >
                + 품목 추가
              </button>
            </div>
            <div className="space-y-2">
              {lines.map((l, i) => (
                <div key={i} className="flex gap-2">
                  <select
                    className={`${inputCls} flex-1`}
                    value={l.item_id}
                    onChange={(e) => setLine(i, { item_id: Number(e.target.value) })}
                  >
                    {items.map((it) => (
                      <option key={it.id} value={it.id}>
                        {it.name} ({won(it.sale_price)})
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min={1}
                    className={`${inputCls} num w-20`}
                    value={l.quantity}
                    onChange={(e) => setLine(i, { quantity: Number(e.target.value) })}
                  />
                  {lines.length > 1 && (
                    <button
                      type="button"
                      onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))}
                      className="px-2 text-ink-3 hover:text-danger"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setOpen(false)} className={btnGhost}>
              취소
            </button>
            <button type="submit" disabled={busy} className={btnPrimary}>
              {busy ? "저장 중…" : "등록"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
