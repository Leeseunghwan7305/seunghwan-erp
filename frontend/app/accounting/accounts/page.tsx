"use client";

import CrudManager, { CrudColumn, Field } from "../../components/CrudManager";
import Badge from "../../components/Badge";
import { api, Account, AccountIn } from "../../lib/api";

const catTone = (c: string) =>
  c === "자산" ? "blue" : c === "부채" ? "red" : c === "자본" ? "amber" : c === "수익" ? "green" : "gray";

const columns: CrudColumn<Account>[] = [
  { key: "code", label: "코드", render: (a) => <span className="num text-ink-3">{a.code}</span> },
  { key: "name", label: "계정과목명", render: (a) => <span className="font-medium">{a.name}</span> },
  { key: "category", label: "구분", align: "center", render: (a) => <Badge tone={catTone(a.category)}>{a.category}</Badge> },
  { key: "entry_side", label: "차/대", align: "center" },
  { key: "memo", label: "비고", render: (a) => <span className="text-ink-3">{a.memo || "-"}</span> },
];

const fields: Field[] = [
  { name: "code", label: "코드", required: true, placeholder: "811", editableOnCreateOnly: true },
  { name: "name", label: "계정과목명", required: true },
  {
    name: "category",
    label: "구분",
    type: "select",
    default: "비용",
    options: ["자산", "부채", "자본", "수익", "비용"].map((c) => ({ value: c, label: c })),
  },
  {
    name: "entry_side",
    label: "차/대",
    type: "select",
    default: "차변",
    options: [
      { value: "차변", label: "차변" },
      { value: "대변", label: "대변" },
    ],
  },
  { name: "memo", label: "비고" },
];

export default function AccountsPage() {
  return (
    <CrudManager<Account>
      eyebrow="Accounting · Chart"
      title="계정과목관리"
      desc="계정과목 체계"
      entityName="계정과목"
      columns={columns}
      fields={fields}
      fetchList={api.accounts}
      create={(v) => api.createAccount(v as unknown as AccountIn)}
      update={(id, v) => api.updateAccount(id, v as unknown as AccountIn)}
      remove={api.deleteAccount}
      getId={(a) => a.id}
      toForm={(a) => ({ code: a.code, name: a.name, category: a.category, entry_side: a.entry_side, memo: a.memo ?? "" })}
    />
  );
}
