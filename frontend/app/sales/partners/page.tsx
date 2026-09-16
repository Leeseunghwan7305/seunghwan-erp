"use client";

import CrudManager, { CrudColumn, Field } from "../../components/CrudManager";
import Badge from "../../components/Badge";
import { api, Partner, PartnerIn } from "../../lib/api";

const columns: CrudColumn<Partner>[] = [
  { key: "name", label: "거래처명", render: (p) => <span className="font-medium">{p.name}</span> },
  {
    key: "kind",
    label: "구분",
    render: (p) => (
      <Badge tone={p.kind === "supplier" ? "blue" : "green"}>
        {p.kind === "supplier" ? "공급처" : "고객"}
      </Badge>
    ),
  },
  { key: "phone", label: "연락처", render: (p) => <span className="num text-ink-2">{p.phone || "-"}</span> },
  { key: "biz_no", label: "사업자번호", render: (p) => <span className="num text-ink-3">{p.biz_no || "-"}</span> },
];

const fields: Field[] = [
  { name: "name", label: "거래처명", required: true, placeholder: "예) 한빛유통" },
  {
    name: "kind",
    label: "구분",
    type: "select",
    required: true,
    default: "supplier",
    options: [
      { value: "supplier", label: "공급처" },
      { value: "customer", label: "고객" },
    ],
  },
  { name: "phone", label: "연락처", placeholder: "02-1234-5678" },
  { name: "biz_no", label: "사업자번호", placeholder: "123-45-67890" },
];

export default function PartnersPage() {
  return (
    <CrudManager<Partner>
      eyebrow="Sales · Partners"
      title="거래처관리"
      desc="공급처·고객 등 거래처 관리"
      entityName="거래처"
      columns={columns}
      fields={fields}
      fetchList={api.partners}
      create={(v) => api.createPartner(v as unknown as PartnerIn)}
      update={(id, v) => api.updatePartner(id, v as unknown as PartnerIn)}
      remove={api.deletePartner}
      getId={(p) => p.id}
      toForm={(p) => ({ name: p.name, kind: p.kind, phone: p.phone ?? "", biz_no: p.biz_no ?? "" })}
    />
  );
}
