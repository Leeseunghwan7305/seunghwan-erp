import { defineConfig, devices } from "@playwright/test";

/**
 * 7단계 E2E — 채팅 스트리밍 플로우 회귀 테스트.
 *
 * 준비:
 *   npm i -D @playwright/test
 *   npx playwright install chromium
 * 실행(백엔드+Ollama+프론트가 떠 있어야 함):
 *   npx playwright test
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
