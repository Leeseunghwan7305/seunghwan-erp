// 화면별 도움말 정의 — 도우미 드로어가 현재 경로로 제목·추천질문을 고른다.
// 답변은 RAG(지식문서)로 생성되므로 여기엔 "무엇을 물을지"만 정의한다.

// manual: 매뉴얼 탭이 RAG에서 이 화면 섹션을 집도록 하는 조회어.
// 화면 UI 사용법(4.x 섹션)에 맞도록 "화면/사용법/방법" 뉘앙스로 적는다. 없으면 title 사용.
export type ScreenHelp = { title: string; questions: string[]; manual?: string };

// 경로 프리픽스 → 도움말. 더 구체적인 경로를 위에 둔다(위에서부터 첫 매치).
const TABLE: { prefix: string; help: ScreenHelp }[] = [
  {
    prefix: "/sales/overview",
    help: {
      title: "영업현황",
      questions: ["영업현황은 무엇을 보여주나요?", "목표 달성률은 어떻게 계산되나요?"],
    },
  },
  {
    prefix: "/sales/orders",
    help: {
      title: "수주현황",
      manual: "수주현황 화면에서 수주 등록하고 확정하는 방법 UI 사용법 재고 반영",
      questions: [
        "수주는 어떻게 등록하나요?",
        "수주를 확정하면 어떻게 되나요?",
        "재고가 부족하면 어떻게 되나요?",
      ],
    },
  },
  {
    prefix: "/sales/partners",
    help: {
      title: "거래처관리",
      manual: "거래처관리 화면에서 거래처 등록하는 방법 UI 사용법 공급처 고객 구분",
      questions: ["거래처는 어떻게 등록하나요?", "공급처와 고객의 차이가 뭔가요?"],
    },
  },
  {
    prefix: "/sales/items",
    help: {
      title: "품목관리",
      manual: "품목관리 화면에서 품목 등록하고 재고 수량 바꾸는 방법 UI 사용법 안전재고",
      questions: [
        "품목은 어떻게 등록하나요?",
        "안전재고가 뭔가요?",
        "재고 수량은 어디서 바꾸나요?",
      ],
    },
  },
  {
    prefix: "/accounting/expenses",
    help: {
      title: "비용관리",
      manual: "비용관리 화면에서 비용 등록하는 방법 UI 사용법 결제수단 계정과목",
      questions: ["비용은 어떻게 등록하나요?", "결제수단은 무엇을 고르나요?"],
    },
  },
  {
    prefix: "/accounting/accounts",
    help: {
      title: "계정과목관리",
      manual: "계정과목관리 화면에서 계정과목 추가하는 방법 UI 사용법 차변 대변 구분",
      questions: [
        "계정과목은 어떻게 추가하나요?",
        "차변과 대변이 뭔가요?",
        "계정 구분(자산·부채·자본·수익·비용)은 어떻게 정하나요?",
      ],
    },
  },
  {
    prefix: "/hr/roles",
    help: {
      title: "권한관리",
      manual: "권한관리 화면에서 역할 만들기 방법 UI 사용법 모듈 접근 권한",
      questions: ["역할은 어떻게 만드나요?", "모듈 권한이 무슨 뜻인가요?"],
    },
  },
  {
    prefix: "/hr/employees",
    help: {
      title: "직원관리",
      manual: "직원관리 화면에서 직원 등록하고 권한 역할 지정하는 방법 UI 사용법",
      questions: ["직원은 어떻게 등록하나요?", "직원에게 권한(역할)은 어떻게 지정하나요?"],
    },
  },
  {
    prefix: "/ai/documents",
    help: {
      title: "지식 문서",
      manual: "지식 문서 화면에서 문서 업로드하는 방법 UI 사용법 AI 검색 인덱싱",
      questions: ["지식 문서는 어떻게 올리나요?", "AI가 문서를 어떻게 찾나요?"],
    },
  },
  {
    prefix: "/chat",
    help: {
      title: "AI 어시스턴트",
      questions: ["AI에게 무엇을 물어볼 수 있나요?", "재고나 매출도 물어볼 수 있나요?"],
    },
  },
  {
    prefix: "/",
    help: {
      title: "대시보드",
      questions: ["대시보드 숫자는 무엇을 뜻하나요?", "미수금과 미지급금이 뭔가요?"],
    },
  },
];

export function screenHelp(pathname: string): ScreenHelp {
  const found = TABLE.find((t) =>
    t.prefix === "/" ? pathname === "/" : pathname.startsWith(t.prefix)
  );
  return (
    found?.help ?? {
      title: "도움말",
      questions: ["이 화면에서 무엇을 할 수 있나요?"],
    }
  );
}
