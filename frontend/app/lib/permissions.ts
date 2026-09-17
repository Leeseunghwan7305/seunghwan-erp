// 권한 모듈 정의 — Role.permissions에 담기는 키와 표시 라벨.
// 사이드바 카테고리와 대응한다. (실제 접근 차단은 로그인 도입 후 단계)
export const MODULES: { key: string; label: string }[] = [
  { key: "dashboard", label: "대시보드" },
  { key: "ai", label: "AI" },
  { key: "sales", label: "영업관리" },
  { key: "accounting", label: "회계관리" },
  { key: "hr", label: "인사관리" },
  { key: "admin", label: "권한관리" },
];

export const moduleLabel = (key: string) =>
  MODULES.find((m) => m.key === key)?.label ?? key;

// 현재 경로가 어느 권한 모듈에 속하는지. (라우트 가드·사이드바 필터 공용)
export function moduleForPath(pathname: string): string {
  if (pathname === "/") return "dashboard";
  if (pathname.startsWith("/chat") || pathname.startsWith("/ai")) return "ai";
  if (pathname.startsWith("/sales")) return "sales";
  if (pathname.startsWith("/accounting")) return "accounting";
  if (pathname.startsWith("/hr/roles")) return "admin";
  if (pathname.startsWith("/hr")) return "hr";
  return "dashboard"; // 정의 안 된 경로는 기본 허용
}

