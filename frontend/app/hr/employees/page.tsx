"use client";

import CrudManager, { CrudColumn, Field, Stat } from "../../components/CrudManager";
import Badge from "../../components/Badge";
import { api, Employee, EmployeeIn } from "../../lib/api";

const empNo = (id: number) => `E-${String(id).padStart(3, "0")}`;

const columns: CrudColumn<Employee>[] = [
  { key: "no", label: "사번", render: (e) => <span className="num text-ink-3">{empNo(e.id)}</span> },
  { key: "name", label: "이름", render: (e) => <span className="font-medium">{e.name}</span> },
  { key: "department", label: "부서", render: (e) => e.department || "-" },
  { key: "position", label: "직급", render: (e) => e.position || "-" },
  { key: "hire_date", label: "입사일", render: (e) => <span className="num text-ink-2">{e.hire_date || "-"}</span> },
  {
    key: "role",
    label: "권한",
    align: "center",
    render: (e) => (e.role_name ? <Badge tone="blue">{e.role_name}</Badge> : <span className="text-ink-3">미지정</span>),
  },
];

const fields: Field[] = [
  { name: "name", label: "이름", required: true },
  { name: "department", label: "부서", placeholder: "영업부" },
  { name: "position", label: "직급", placeholder: "사원" },
  { name: "hire_date", label: "입사일", type: "date" },
  {
    name: "role_id",
    label: "권한(역할)",
    type: "select",
    loadOptions: async () => [
      { value: "", label: "(미지정)" },
      ...(await api.roles()).map((r) => ({ value: String(r.id), label: r.name })),
    ],
  },
];

const stats = (rows: Employee[]): Stat[] => {
  const depts = new Set(rows.map((e) => e.department).filter(Boolean));
  const assigned = rows.filter((e) => e.role_id).length;
  return [
    { label: "전체 인원", value: `${rows.length}명` },
    { label: "부서 수", value: `${depts.size}개`, accent: "green" },
    { label: "권한 지정", value: `${assigned}명`, accent: "blue" },
  ];
};

export default function EmployeesPage() {
  return (
    <CrudManager<Employee>
      eyebrow="HR · Roster"
      title="직원관리"
      desc="임직원 명부 · 권한(역할) 지정"
      entityName="직원"
      columns={columns}
      fields={fields}
      stats={stats}
      fetchList={api.employees}
      create={(v) =>
        api.createEmployee({
          name: String(v.name),
          department: (v.department as string) || null,
          position: (v.position as string) || null,
          hire_date: (v.hire_date as string) || null,
          role_id: v.role_id ? Number(v.role_id) : null,
        })
      }
      update={(id, v) =>
        api.updateEmployee(id, {
          name: String(v.name),
          department: (v.department as string) || null,
          position: (v.position as string) || null,
          hire_date: (v.hire_date as string) || null,
          role_id: v.role_id ? Number(v.role_id) : null,
        })
      }
      remove={api.deleteEmployee}
      getId={(e) => e.id}
      toForm={(e) => ({
        name: e.name,
        department: e.department ?? "",
        position: e.position ?? "",
        hire_date: e.hire_date ?? "",
        role_id: e.role_id ? String(e.role_id) : "",
      })}
    />
  );
}
