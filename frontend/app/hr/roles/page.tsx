"use client";

import CrudManager, { CrudColumn, Field } from "../../components/CrudManager";
import Badge from "../../components/Badge";
import { api, Role, RoleIn } from "../../lib/api";
import { MODULES, moduleLabel } from "../../lib/permissions";

const columns: CrudColumn<Role>[] = [
  { key: "name", label: "역할명", render: (r) => <span className="font-medium">{r.name}</span> },
  { key: "description", label: "설명", render: (r) => <span className="text-ink-2">{r.description || "-"}</span> },
  {
    key: "permissions",
    label: "접근 모듈",
    render: (r) =>
      r.permissions.length ? (
        <div className="flex flex-wrap gap-1">
          {r.permissions.map((p) => (
            <Badge key={p} tone="blue">
              {moduleLabel(p)}
            </Badge>
          ))}
        </div>
      ) : (
        <span className="text-ink-3">-</span>
      ),
  },
];

const fields: Field[] = [
  { name: "name", label: "역할명", required: true, placeholder: "예) 매니저" },
  { name: "description", label: "설명" },
  {
    name: "permissions",
    label: "접근 가능한 모듈",
    type: "checkboxes",
    options: MODULES.map((m) => ({ value: m.key, label: m.label })),
  },
];

export default function RolesPage() {
  return (
    <CrudManager<Role>
      eyebrow="HR · Roles"
      title="권한관리"
      desc="역할별 접근 가능한 모듈을 설정합니다. (직원관리에서 직원에게 역할 지정 · 실제 접근 차단은 로그인 도입 후)"
      entityName="역할"
      columns={columns}
      fields={fields}
      fetchList={api.roles}
      create={(v) => api.createRole(v as unknown as RoleIn)}
      update={(id, v) => api.updateRole(id, v as unknown as RoleIn)}
      remove={api.deleteRole}
      getId={(r) => r.id}
      toForm={(r) => ({ name: r.name, description: r.description ?? "", permissions: r.permissions })}
    />
  );
}
