"use client";

import CrudManager, { CrudColumn, Field, Stat } from "../../components/CrudManager";
import Badge from "../../components/Badge";
import { api, Expense, ExpenseIn, won } from "../../lib/api";

const methodTone = (m: string) => (m === "법인카드" ? "blue" : m === "현금" ? "amber" : "gray");

const columns: CrudColumn<Expense>[] = [
  { key: "expense_date", label: "일자", render: (e) => <span className="num text-ink-2">{e.expense_date}</span> },
  { key: "account", label: "계정과목", render: (e) => <span className="font-medium">{e.account}</span> },
  { key: "memo", label: "적요", render: (e) => e.memo || "-" },
  { key: "dept", label: "부서", render: (e) => e.dept || "-" },
  { key: "method", label: "결제수단", align: "center", render: (e) => <Badge tone={methodTone(e.method)}>{e.method}</Badge> },
  { key: "amount", label: "금액", align: "right", render: (e) => won(e.amount) },
];

const fields: Field[] = [
  { name: "expense_date", label: "일자", type: "date", required: true },
  { name: "account", label: "계정과목", required: true, placeholder: "임차료" },
  { name: "memo", label: "적요" },
  { name: "dept", label: "부서", placeholder: "총무" },
  {
    name: "method",
    label: "결제수단",
    type: "select",
    default: "법인카드",
    options: ["법인카드", "현금", "계좌이체"].map((m) => ({ value: m, label: m })),
  },
  { name: "amount", label: "금액", type: "number", default: 0 },
];

const stats = (rows: Expense[]): Stat[] => {
  const total = rows.reduce((a, e) => a + e.amount, 0);
  return [
    { label: "총 지출", value: won(total), accent: "red" },
    { label: "지출 건수", value: `${rows.length}건` },
  ];
};

export default function ExpensesPage() {
  return (
    <CrudManager<Expense>
      eyebrow="Accounting · Expenses"
      title="비용관리"
      desc="지출(비용) 내역"
      entityName="비용"
      columns={columns}
      fields={fields}
      stats={stats}
      fetchList={api.expenses}
      create={(v) => api.createExpense(v as unknown as ExpenseIn)}
      update={(id, v) => api.updateExpense(id, v as unknown as ExpenseIn)}
      remove={api.deleteExpense}
      getId={(e) => e.id}
      toForm={(e) => ({
        expense_date: e.expense_date,
        account: e.account,
        memo: e.memo ?? "",
        dept: e.dept ?? "",
        method: e.method,
        amount: e.amount,
      })}
    />
  );
}
