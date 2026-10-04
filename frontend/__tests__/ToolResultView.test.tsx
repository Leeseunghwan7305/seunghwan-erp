import { render, screen } from "@testing-library/react";
import ToolResultView from "../app/components/ToolResultView";

describe("ToolResultView (Generative UI)", () => {
  it("재고 결과를 표로 렌더하고 미달 품목을 표시한다", () => {
    const rows = [
      { 코드: "A-1", 품명: "생수 500ml", 현재재고: 5, 안전재고: 10, 판매가: 6000, 안전재고미달: true },
    ];
    render(<ToolResultView name="get_inventory" data={rows} />);
    expect(screen.getByText("생수 500ml")).toBeInTheDocument();
    expect(screen.getByText("미달")).toBeInTheDocument();
  });

  it("차트 스펙을 막대 그래프 제목으로 렌더한다", () => {
    const data = { chart: { type: "bar", title: "품목별 재고", unit: "개", data: [{ label: "생수", value: 300 }] } };
    render(<ToolResultView name="get_chart" data={data} />);
    expect(screen.getByText("품목별 재고")).toBeInTheDocument();
  });
});
