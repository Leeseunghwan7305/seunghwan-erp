import { render, screen } from "@testing-library/react";
import Markdown from "../app/components/Markdown";

describe("Markdown (경량 렌더러)", () => {
  it("굵게·인라인 코드·목록을 렌더한다", () => {
    render(<Markdown text={"**굵게** 와 `코드`\n\n- 항목1\n- 항목2"} />);
    expect(screen.getByText("굵게").tagName).toBe("STRONG");
    expect(screen.getByText("코드").tagName).toBe("CODE");
    expect(screen.getByText("항목1")).toBeInTheDocument();
  });

  it("XSS: 안전하지 않은 링크는 원문으로 남긴다", () => {
    render(<Markdown text={"[클릭](javascript:alert(1))"} />);
    // javascript: 링크는 <a>로 만들지 않음 → 앵커가 없어야 함
    expect(screen.queryByRole("link")).toBeNull();
  });
});
