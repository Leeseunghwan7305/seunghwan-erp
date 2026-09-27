"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * 2단계: TanStack Query 프로바이더.
 *
 * 스트리밍 답변 자체는 직접 reader로 관리하지만, '대화 목록'처럼 읽기·캐시가
 * 자연스러운 데이터는 Query로 다룬다(목록 조회·생성·삭제 시 자동 무효화).
 */
export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 5_000, refetchOnWindowFocus: false } },
      })
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
