"use client";

import { ReactNode, useEffect, useState } from "react";
import PageHeader from "./PageHeader";
import DataTable, { Column } from "./DataTable";
import StatCard from "./StatCard";
import Modal from "./Modal";

export type Field = {
  name: string;
  label: string;
  type?: "text" | "number" | "select" | "date";
  options?: { value: string; label: string }[];
  required?: boolean;
  placeholder?: string;
  default?: string | number;
  editableOnCreateOnly?: boolean; // 수정 시 비활성 (예: 코드)
};

export type CrudColumn<T> = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  render?: (row: T) => ReactNode;
};

export type Stat = { label: string; value: string; hint?: string; accent?: "red" | "amber" | "green" | "blue" };

const inputCls =
  "w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none";
const btnPrimary =
  "rounded-md bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50";
const btnGhost =
  "rounded-md border border-line-strong px-4 py-2 text-sm text-ink-2 transition-colors hover:bg-surface-2";

export default function CrudManager<T>({
  eyebrow,
  title,
  desc,
  entityName,
  columns,
  fields,
  fetchList,
  create,
  update,
  remove,
  getId,
  toForm,
  stats,
}: {
  eyebrow: string;
  title: string;
  desc?: string;
  entityName: string;
  columns: CrudColumn<T>[];
  fields: Field[];
  fetchList: () => Promise<T[]>;
  create: (values: Record<string, string | number | null>) => Promise<unknown>;
  update: (id: number, values: Record<string, string | number | null>) => Promise<unknown>;
  remove: (id: number) => Promise<void>;
  getId: (row: T) => number;
  toForm: (row: T) => Record<string, string | number | null>;
  stats?: (rows: T[]) => Stat[];
}) {
  const [rows, setRows] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [values, setValues] = useState<Record<string, string | number | null>>({});
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    fetchList()
      .then((r) => {
        setRows(r);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const openCreate = () => {
    const init: Record<string, string | number | null> = {};
    fields.forEach((f) => (init[f.name] = f.default ?? (f.type === "number" ? 0 : "")));
    setValues(init);
    setEditing(null);
    setOpen(true);
  };
  const openEdit = (row: T) => {
    setValues(toForm(row));
    setEditing(row);
    setOpen(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload: Record<string, string | number | null> = {};
      fields.forEach((f) => {
        const v = values[f.name];
        payload[f.name] = f.type === "number" ? Number(v || 0) : v === "" ? null : v;
      });
      if (editing) await update(getId(editing), payload);
      else await create(payload);
      setOpen(false);
      load();
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const del = async (row: T) => {
    if (!confirm(`${entityName}을(를) 삭제하시겠습니까?`)) return;
    try {
      await remove(getId(row));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const tableColumns: Column[] = [
    ...columns.map((c) => ({ key: c.key, label: c.label, align: c.align })),
    { key: "__act", label: "관리", align: "right" as const },
  ];
  const tableRows: Record<string, ReactNode>[] = rows.map((r) => {
    const o: Record<string, ReactNode> = {};
    columns.forEach((c) => {
      o[c.key] = c.render ? c.render(r) : ((r as Record<string, ReactNode>)[c.key] ?? "");
    });
    o.__act = (
      <div className="flex justify-end gap-1.5">
        <button
          onClick={() => openEdit(r)}
          className="rounded border border-line-strong px-2 py-1 text-xs text-ink-2 transition-colors hover:bg-surface-2"
        >
          수정
        </button>
        <button
          onClick={() => del(r)}
          className="rounded border border-line-strong px-2 py-1 text-xs text-danger transition-colors hover:bg-danger-tint"
        >
          삭제
        </button>
      </div>
    );
    return o;
  });

  const statList = stats && rows.length > 0 ? stats(rows) : [];

  return (
    <div>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        desc={desc}
        meta={
          <>
            총 <span className="num text-ink">{rows.length}</span>건
          </>
        }
      />

      {statList.length > 0 && (
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          {statList.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>
      )}

      <div className="mb-3 flex justify-end">
        <button onClick={openCreate} className={btnPrimary}>
          + {entityName} 등록
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-card border border-danger/30 bg-danger-tint px-4 py-3 text-sm text-danger">
          오류: {error} · 백엔드(localhost:8000) 실행 여부를 확인하세요.
        </div>
      )}

      {loading ? (
        <p className="text-sm text-ink-2">불러오는 중…</p>
      ) : (
        <DataTable columns={tableColumns} rows={tableRows} />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={`${entityName} ${editing ? "수정" : "등록"}`}
      >
        <form onSubmit={submit} className="space-y-4">
          {fields.map((f) => {
            const disabled = f.editableOnCreateOnly && editing !== null;
            return (
              <label key={f.name} className="block">
                <span className="mb-1.5 block text-xs font-medium text-ink-2">
                  {f.label}
                  {f.required && <span className="text-danger"> *</span>}
                </span>
                {f.type === "select" ? (
                  <select
                    className={inputCls}
                    value={String(values[f.name] ?? "")}
                    required={f.required}
                    disabled={disabled}
                    onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  >
                    {f.options?.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className={`${inputCls} ${f.type === "number" ? "num" : ""}`}
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                    value={String(values[f.name] ?? "")}
                    placeholder={f.placeholder}
                    required={f.required}
                    disabled={disabled}
                    onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
                  />
                )}
              </label>
            );
          })}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={() => setOpen(false)} className={btnGhost}>
              취소
            </button>
            <button type="submit" disabled={busy} className={btnPrimary}>
              {busy ? "저장 중…" : editing ? "수정" : "등록"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
