"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Employee } from "../lib/api";
import { useAuth } from "../components/AuthProvider";

export default function LoginPage() {
  const router = useRouter();
  const { login, user } = useAuth();
  const [emps, setEmps] = useState<Employee[]>([]);
  const [sel, setSel] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .employees()
      .then((e) => {
        setEmps(e);
        setSel(e[0]?.id ?? "");
      })
      .catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (user) router.replace("/");
  }, [user, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sel) return;
    setBusy(true);
    try {
      const emp = emps.find((x) => x.id === Number(sel));
      if (emp) {
        await login(emp);
        router.push("/");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-paper px-4">
      <div className="w-full max-w-sm rounded-card border border-line bg-surface p-8">
        <div className="mb-6 flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-brand font-mono text-[15px] font-semibold text-white">
            E
          </span>
          <div className="leading-tight">
            <div className="font-semibold text-ink">제조 ERP</div>
            <div className="eyebrow">Ledger · Login</div>
          </div>
        </div>

        <p className="mb-5 text-sm text-ink-2">직원을 선택해 로그인하세요.</p>

        {err && (
          <div className="mb-3 rounded-md border border-danger/30 bg-danger-tint px-3 py-2 text-sm text-danger">
            {err}
          </div>
        )}

        <form onSubmit={submit} className="space-y-4">
          <select
            className="w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none"
            value={sel}
            onChange={(e) => setSel(Number(e.target.value))}
          >
            {emps.length === 0 && <option value="">직원 데이터를 불러오는 중…</option>}
            {emps.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name} · {e.department ?? "-"}
                {e.role_name ? ` (${e.role_name})` : " (권한 미지정)"}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy || !sel}
            className="w-full rounded-md bg-brand px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {busy ? "로그인 중…" : "로그인"}
          </button>
        </form>
      </div>
    </div>
  );
}
