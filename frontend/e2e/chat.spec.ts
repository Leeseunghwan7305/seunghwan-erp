import { test, expect } from "@playwright/test";

/**
 * 채팅 스트리밍 UX 회귀 테스트 (로컬 Ollama 기준).
 *
 * 커버: 로딩 상태 → 스트리밍 응답 → 중지 버튼 → 재시도. (로드맵 1·4·5단계)
 * 백엔드(:8000)·Ollama(:11434)·프론트(:3000)가 실행 중이어야 한다.
 */

test.beforeEach(async ({ page }) => {
  await page.goto("/chat");
  // 로컬 모델로 전환(무료·오프라인, 결정적).
  await page.getByRole("button", { name: "로컬 LLM" }).click();
});

test("질문을 보내면 답변이 스트리밍되어 렌더된다", async ({ page }) => {
  const input = page.getByRole("textbox", { name: /안전재고 미달/ });
  await input.fill("안전재고가 뭔지 한 문장으로 설명해줘");
  await input.press("Enter");

  // 생성 중에는 '중지' 버튼이 보인다(4단계 상태 UI).
  await expect(page.getByRole("button", { name: "중지" })).toBeVisible();

  // 답변이 도착하면 '중지'가 사라지고, 근거 배지 + 본문이 렌더된다.
  await expect(page.getByRole("button", { name: "중지" })).toBeHidden({ timeout: 60_000 });
  await expect(page.getByText("근거").first()).toBeVisible();
  await expect(page.getByText(/안전재고/)).toBeVisible();
});

test("생성 중 중지를 누르면 즉시 멈춘다", async ({ page }) => {
  const input = page.getByRole("textbox", { name: /안전재고 미달/ });
  await input.fill("재고 관리 방법을 아주 길고 자세히 설명해줘");
  await input.press("Enter");

  const stopBtn = page.getByRole("button", { name: "중지" });
  await expect(stopBtn).toBeVisible();
  await stopBtn.click();

  // 중지 후 입력이 다시 활성화된다(busy 해제).
  await expect(page.getByRole("button", { name: "전송" })).toBeVisible();
});
