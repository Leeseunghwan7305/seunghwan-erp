import StatCard from "../../components/StatCard";
import DataTable, { Column } from "../../components/DataTable";
import PageHeader from "../../components/PageHeader";

const won = (n: number) => `₩${n.toLocaleString("ko-KR")}`;

const columns: Column[] = [
  { key: "month", label: "월" },
  { key: "sales", label: "매출", align: "right" },
  { key: "orders", label: "수주건수", align: "right" },
  { key: "avg", label: "평균단가", align: "right" },
  { key: "rate", label: "목표달성", align: "right" },
];

const monthly = [
  { month: "2026-05", sales: 12400000, orders: 42, avg: 295000, rate: "103%" },
  { month: "2026-06", sales: 11800000, orders: 39, avg: 302000, rate: "98%" },
  { month: "2026-07", sales: 13950000, orders: 47, avg: 296000, rate: "112%" },
  { month: "2026-08", sales: 12100000, orders: 41, avg: 295000, rate: "95%" },
  { month: "2026-09", sales: 8650000, orders: 28, avg: 308000, rate: "72%" },
];

export default function SalesOverviewPage() {
  const rows = monthly.map((m) => ({
    month: <span className="num font-medium">{m.month}</span>,
    sales: won(m.sales),
    orders: `${m.orders}건`,
    avg: won(m.avg),
    rate: m.rate,
  }));

  return (
    <div>
      <PageHeader
        eyebrow="Sales · 2026-09"
        title="영업현황"
        desc="이번 달 매출·수주 지표 요약"
      />

      <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="이번 달 매출" value={won(8650000)} hint="전월 대비 -28%" accent="amber" />
        <StatCard label="수주 건수" value="28건" hint="진행중 5건" />
        <StatCard label="목표 달성률" value="72%" hint="목표 ₩12,000,000" accent="red" />
        <StatCard label="신규 거래처" value="3곳" hint="이번 달" accent="green" />
      </div>

      <div className="mb-3 flex items-center gap-3">
        <span className="eyebrow">월별 매출 추이</span>
        <span className="h-px flex-1 bg-line" />
      </div>
      <DataTable columns={columns} rows={rows} />
    </div>
  );
}
