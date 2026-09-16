"use client";

import CrudManager, { CrudColumn, Field } from "../../components/CrudManager";
import Badge from "../../components/Badge";
import { api, Item, won } from "../../lib/api";

const columns: CrudColumn<Item>[] = [
  { key: "code", label: "코드", render: (i) => <span className="num text-ink-3">{i.code}</span> },
  { key: "name", label: "품명", render: (i) => <span className="font-medium">{i.name}</span> },
  { key: "unit", label: "단위", align: "center" },
  { key: "purchase_price", label: "매입가", align: "right", render: (i) => won(i.purchase_price) },
  { key: "sale_price", label: "판매가", align: "right", render: (i) => won(i.sale_price) },
  {
    key: "quantity",
    label: "재고",
    align: "right",
    render: (i) =>
      i.below_safety ? <span className="num font-medium text-danger">{i.quantity}</span> : <span className="num">{i.quantity}</span>,
  },
  {
    key: "safety_stock",
    label: "안전재고",
    align: "center",
    render: (i) => (i.below_safety ? <Badge tone="red">미달 {i.safety_stock}</Badge> : <span className="num text-ink-3">{i.safety_stock}</span>),
  },
];

const fields: Field[] = [
  { name: "code", label: "코드", required: true, placeholder: "A-001", editableOnCreateOnly: true },
  { name: "name", label: "품명", required: true },
  { name: "unit", label: "단위", default: "EA" },
  { name: "purchase_price", label: "매입가", type: "number", default: 0 },
  { name: "sale_price", label: "판매가", type: "number", default: 0 },
  { name: "safety_stock", label: "안전재고", type: "number", default: 0 },
  { name: "quantity", label: "재고 수량", type: "number", default: 0 },
];

export default function SalesItemsPage() {
  return (
    <CrudManager<Item>
      eyebrow="Sales · Items"
      title="품목관리"
      desc="판매 품목 단가·재고 관리"
      entityName="품목"
      columns={columns}
      fields={fields}
      fetchList={api.items}
      create={(v) =>
        api.createItem({
          code: String(v.code),
          name: String(v.name),
          unit: String(v.unit || "EA"),
          purchase_price: Number(v.purchase_price || 0),
          sale_price: Number(v.sale_price || 0),
          safety_stock: Number(v.safety_stock || 0),
          initial_stock: Number(v.quantity || 0),
        })
      }
      update={(id, v) =>
        api.updateItem(id, {
          name: String(v.name),
          unit: String(v.unit || "EA"),
          purchase_price: Number(v.purchase_price || 0),
          sale_price: Number(v.sale_price || 0),
          safety_stock: Number(v.safety_stock || 0),
          quantity: Number(v.quantity || 0),
        })
      }
      remove={api.deleteItem}
      getId={(i) => i.id}
      toForm={(i) => ({
        code: i.code,
        name: i.name,
        unit: i.unit,
        purchase_price: i.purchase_price,
        sale_price: i.sale_price,
        safety_stock: i.safety_stock,
        quantity: i.quantity,
      })}
    />
  );
}
