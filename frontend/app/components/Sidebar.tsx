"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// 메인은 카테고리가 아닌 최상위 링크 묶음, 나머지는 카테고리로 분류.
const groups: { title: string; items: { href: string; label: string }[] }[] = [
  {
    title: "메인",
    items: [{ href: "/", label: "대시보드" }],
  },
  {
    title: "AI",
    items: [
      { href: "/chat", label: "AI 어시스턴트" },
      { href: "/ai/documents", label: "지식 문서" },
    ],
  },
  {
    title: "영업관리",
    items: [
      { href: "/sales/overview", label: "영업현황" },
      { href: "/sales/orders", label: "수주현황" },
      { href: "/sales/partners", label: "거래처관리" },
      { href: "/sales/items", label: "품목관리" },
    ],
  },
  {
    title: "회계관리",
    items: [
      { href: "/accounting/expenses", label: "비용관리" },
      { href: "/accounting/accounts", label: "계정과목관리" },
    ],
  },
  {
    title: "인사관리",
    items: [{ href: "/hr/employees", label: "직원관리" }],
  },
];

export default function Sidebar() {
  const pathname = usePathname();

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
        {groups.map((g) => (
          <div key={g.title}>
            <div className="eyebrow !text-rail-dim px-3 pb-2">{g.title}</div>
            <div className="flex flex-col gap-0.5">
              {g.items.map((n) => {
                const active =
                  n.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(n.href);
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
                    {/* 활성 표시 · 좌측 그린 스파인 */}
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
      <p className="px-6 py-5 text-[11px] leading-relaxed text-rail-dim">
        제조 ERP
        <br />
        <span className="num">v0.1</span> · 프로토타입
      </p>
    </aside>
  );
}
