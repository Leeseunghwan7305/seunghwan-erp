"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

// 각 항목에 권한 모듈 키(module)를 부여 — 해당 권한이 있는 항목만 노출된다.
const groups: {
  title: string;
  items: { href: string; label: string; module: string }[];
}[] = [
  {
    title: "메인",
    items: [{ href: "/", label: "대시보드", module: "dashboard" }],
  },
  {
    title: "AI",
    items: [
      { href: "/chat", label: "AI 어시스턴트", module: "ai" },
      { href: "/ai/documents", label: "지식 문서", module: "ai" },
    ],
  },
  {
    title: "영업관리",
    items: [
      { href: "/sales/overview", label: "영업현황", module: "sales" },
      { href: "/sales/orders", label: "수주현황", module: "sales" },
      { href: "/sales/partners", label: "거래처관리", module: "sales" },
      { href: "/sales/items", label: "품목관리", module: "sales" },
    ],
  },
  {
    title: "회계관리",
    items: [
      { href: "/accounting/expenses", label: "비용관리", module: "accounting" },
      { href: "/accounting/accounts", label: "계정과목관리", module: "accounting" },
    ],
  },
  {
    title: "인사관리",
    items: [
      { href: "/hr/employees", label: "직원관리", module: "hr" },
      { href: "/hr/roles", label: "권한관리", module: "admin" },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, hasPermission } = useAuth();

  const visibleGroups = groups
    .map((g) => ({ ...g, items: g.items.filter((i) => hasPermission(i.module)) }))
    .filter((g) => g.items.length > 0);

  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col bg-rail text-rail-ink">
      {/* 워드마크 */}
      <div className="flex items-center gap-3 px-6 pb-5 pt-7">
        <span className="grid h-9 w-9 place-items-center rounded-md bg-brand font-mono text-[15px] font-semibold text-white">
          E
        </span>
        <div className="leading-tight">
          <div className="font-semibold tracking-tight">ERP</div>
          <div className="eyebrow !text-rail-dim">Ledger</div>
        </div>
      </div>

      <div className="mx-6 border-t border-[var(--rail-line)]" />

      <nav className="flex flex-1 flex-col gap-6 overflow-y-auto px-4 py-6">
        {visibleGroups.map((g) => (
          <div key={g.title}>
            <div className="eyebrow !text-rail-dim px-3 pb-2">{g.title}</div>
            <div className="flex flex-col gap-0.5">
              {g.items.map((n) => {
                const active =
                  n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
                return (
                  <Link
                    key={n.href}
                    href={n.href}
                    className={`group relative flex items-center rounded-md px-3 py-2 text-sm transition-colors ${
                      active
                        ? "bg-rail-2 text-rail-ink"
                        : "text-rail-dim hover:bg-rail-2 hover:text-rail-ink"
                    }`}
                  >
                    <span
                      className={`absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-brand transition-opacity ${
                        active ? "opacity-100" : "opacity-0"
                      }`}
                    />
                    {n.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="mx-6 border-t border-[var(--rail-line)]" />
      {/* 현재 사용자 · 로그아웃 */}
      <div className="px-5 py-4">
        <div className="mb-2 leading-tight">
          <div className="text-sm font-medium text-rail-ink">{user?.name ?? "게스트"}</div>
          <div className="eyebrow !text-rail-dim">{user?.role_name ?? "권한 미지정"}</div>
        </div>
        <button
          onClick={() => {
            logout();
            router.push("/login");
          }}
          className="w-full rounded-md border border-[var(--rail-line)] px-3 py-1.5 text-xs text-rail-dim transition-colors hover:bg-rail-2 hover:text-rail-ink"
        >
          로그아웃
        </button>
      </div>
    </aside>
  );
}
