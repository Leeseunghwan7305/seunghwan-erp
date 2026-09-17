"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import Sidebar from "./Sidebar";
import { moduleForPath } from "../lib/permissions";

function Center({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center text-sm text-ink-2">{children}</div>
  );
}

function NoPermission() {
  return (
    <div className="rounded-card border border-dashed border-line-strong bg-surface px-6 py-16 text-center">
      <div className="eyebrow mb-3">403</div>
      <h1 className="mb-1 text-lg font-semibold text-ink">접근 권한이 없습니다</h1>
      <p className="text-sm text-ink-2">
        이 메뉴에 접근할 권한이 없습니다. 관리자에게 문의하세요.
      </p>
    </div>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, ready, hasPermission } = useAuth();

  const isLogin = pathname === "/login";

  useEffect(() => {
    if (ready && !user && !isLogin) router.replace("/login");
  }, [ready, user, isLogin, router]);

  if (!ready) return <Center>불러오는 중…</Center>;

  // 로그인 페이지는 사이드바 없이 단독 렌더
  if (isLogin) return <>{children}</>;

  // 미로그인 → 리다이렉트 대기(깜빡임 방지)
  if (!user) return <Center>로그인으로 이동 중…</Center>;

  const allowed = hasPermission(moduleForPath(pathname));

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="min-w-0 flex-1 px-8 py-9 md:px-12">
        <div className="mx-auto max-w-6xl">{allowed ? children : <NoPermission />}</div>
      </main>
    </div>
  );
}
