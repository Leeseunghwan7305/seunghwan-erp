"use client";

import { useEffect, useState } from "react";
import { api, DashboardSummary, Item, won } from "./lib/api";
import PageHeader from "./components/PageHeader";
import StatCard from "./components/StatCard";
import { HBars, Donut, Panel, Legend, BarRow } from "./components/charts";

// 큰 금액은 백만 단위로 축약 (차트 라벨 가독성).
// 품목이 많아도 대시보드가 길어지지 않도록 상위 N종만 노출(전체는 품목관리 페이지).
const INV_LIMIT = 12;
const ASSET_LIMIT = 10;

const compact = (n: number) =>
  n >= 1_000_000
    ? `₩ ${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`
    : won(n);

// 섹션 구분자 — mono 눈썹 + 헤어라인으로 장부의 "구획"을 표현.
function SectionLabel({ children }: { children: string }) {
  return (
    <div className="mb-3 flex items-center gap-3">
      <span className="eyebrow">{children}</span>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [items, setItems] = useState<Item[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.dashboard(), api.items()])
      .then(([d, i]) => {
        setData(d);
        setItems(i);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="대시보드"
        desc="제조 ERP — 매출·재고·정산을 한눈에."
        meta={
          <span className="num rounded-full border border-line bg-surface px-3 py-1 text-[11px] text-ink-3">
            기준 2026-09-16
          </span>
        }
      />

      {error && (
        <div className="rounded-card border border-danger/40 bg-danger-tint p-4 text-sm text-danger">
          <span className="font-medium">API에 연결할 수 없습니다.</span> {error}
          <div className="mt-1 text-ink-2">
            백엔드(<span className="num">localhost:8000</span>)가 실행 중인지 확인하세요.
          </div>
        </div>
      )}

      {!(data && items) && !error && (
        <div className="space-y-8">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-[104px] animate-pulse rounded-card border border-line bg-surface-2"
              />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            <div className="h-[280px] animate-pulse rounded-card border border-line bg-surface-2 lg:col-span-2" />
            <div className="h-[280px] animate-pulse rounded-card border border-line bg-surface-2" />
          </div>
        </div>
      )}

      {data && items && (
        <div className="space-y-8">
          {/* ── KPI 히어로 ── */}
          <section>
            <SectionLabel>매출 · 정산</SectionLabel>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="총 매출" value={won(data.sales_total)} accent="green" hint="정산 완료 기준" />
              <StatCard label="총 매입" value={won(data.purchase_total)} accent="amber" hint="정산 완료 기준" />
              <StatCard label="미지급금" value={won(data.payable)} accent="red" hint="미결제 매입" />
              <StatCard
                label="진행 중 주문"
                value={`${data.open_orders}건`}
                accent="blue"
                hint={`미수금 ${won(data.receivable)}`}
              />
            </div>
          </section>

          {/* ── 재고 운영 뷰 ── */}
          <section>
            <SectionLabel>재고 현황</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <Panel
                  title="품목별 재고 현황"
                  aside={
                    <span>
                      안전재고 미달{" "}
                      <span className="num font-medium text-danger">
                        {data.below_safety_count}종
                      </span>
                    </span>
                  }
                >
                  <HBars
                    format={(n) => n.toLocaleString("ko-KR")}
                    rows={inventoryRows(items).slice(0, INV_LIMIT)}
                  />
                  <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3">
                    <Legend
                      items={[
                        { label: "정상 재고", tone: "brand" },
                        { label: "안전재고 미달", tone: "danger" },
                        { label: "안전재고선", tone: "ink", kind: "line" },
                      ]}
                    />
                    {items.length > INV_LIMIT && (
                      <span className="shrink-0 text-[11px] text-ink-3">
                        미달 우선 · 상위 {INV_LIMIT}종 · 외{" "}
                        <span className="num">{items.length - INV_LIMIT}</span>종
                      </span>
                    )}
                  </div>
                </Panel>
              </div>

              <Panel
                title="재고 건전성"
                aside={`총 ${data.total_stock_qty.toLocaleString("ko-KR")}개`}
              >
                <Donut
                  centerValue={`${data.item_count}종`}
                  centerLabel="등록 품목"
                  segments={[
                    {
                      label: "정상",
                      value: data.item_count - data.below_safety_count,
                      tone: "brand",
                    },
                    { label: "미달", value: data.below_safety_count, tone: "danger" },
                  ]}
                />
              </Panel>
            </div>
          </section>

          {/* ── 재고 자산 · 채권채무 ── */}
          <section>
            <SectionLabel>재고 자산 · 정산</SectionLabel>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <Panel
                  title="재고 자산 (매입원가 기준)"
                  aside={
                    <span>
                      평가액 합{" "}
                      <span className="num font-medium text-ink">
                        {won(assetTotal(items))}
                      </span>
                    </span>
                  }
                >
                  <HBars format={compact} rows={assetRows(items).slice(0, ASSET_LIMIT)} />
                  {items.length > ASSET_LIMIT && (
                    <div className="mt-4 flex items-center justify-between border-t border-line pt-3 text-[11px] text-ink-3">
                      <span>
                        상위 {ASSET_LIMIT}종 · 외{" "}
                        <span className="num">{items.length - ASSET_LIMIT}</span>종
                      </span>
                      <span>
                        나머지 합{" "}
                        <span className="num text-ink-2">
                          {won(
                            assetTotal(items) -
                              assetRows(items)
                                .slice(0, ASSET_LIMIT)
                                .reduce((a, r) => a + r.value, 0)
                          )}
                        </span>
                      </span>
                    </div>
                  )}
                </Panel>
              </div>

              <Panel title="채권 · 채무">
                <HBars
                  labelWidth="4.5rem"
                  format={compact}
                  rows={[
                    { label: "미수금", value: data.receivable, tone: "brand" },
                    { label: "미지급금", value: data.payable, tone: "danger" },
                  ]}
                />
                <div className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4">
                  <div>
                    <div className="text-[11px] text-ink-3">받을 돈</div>
                    <div className="num mt-0.5 text-lg font-semibold text-brand">
                      {won(data.receivable)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[11px] text-ink-3">줄 돈</div>
                    <div className="num mt-0.5 text-lg font-semibold text-danger">
                      {won(data.payable)}
                    </div>
                  </div>
                </div>
              </Panel>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

/* ── 파생 데이터 ── */

function inventoryRows(items: Item[]): BarRow[] {
  return items.map((it) => ({
    label: it.name,
    value: it.quantity,
    marker: it.safety_stock,
    tone: it.below_safety ? "danger" : "brand",
    pill: it.below_safety ? { text: "미달", tone: "danger" } : undefined,
  }));
}

function assetRows(items: Item[]): BarRow[] {
  return [...items]
    .map((it) => ({
      label: it.name,
      value: it.quantity * it.purchase_price,
      tone: "brand" as const,
    }))
    .sort((a, b) => b.value - a.value);
}

function assetTotal(items: Item[]): number {
  return items.reduce((a, it) => a + it.quantity * it.purchase_price, 0);
}
