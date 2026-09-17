import type { Metadata } from "next";
import { IBM_Plex_Sans_KR, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./components/AuthProvider";
import Shell from "./components/Shell";

// UI·한글 본문. 엔지니어링된 지오메트릭 산세 — 시스템 폰트 탈출.
const sans = IBM_Plex_Sans_KR({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

// 숫자·코드·라벨 전용 고정폭. tabular 정렬이 이 앱의 시그니처.
const mono = IBM_Plex_Mono({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "제조 ERP 프로토타입",
  description: "Next.js + FastAPI + PostgreSQL ERP 프로토타입",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <AuthProvider>
          <Shell>{children}</Shell>
        </AuthProvider>
      </body>
    </html>
  );
}
