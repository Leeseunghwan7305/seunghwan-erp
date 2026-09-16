# AI 챗봇 붙이기 설계 (2026-09-16)

> 상태: **Phase A 구현·검증 완료 (2026-09-16).** TODO.md의 3개 항목(구독 연결·모델 라우팅·도구)을 챗봇 하나로 통합했다.
> Claude 쿠키 경로의 실호출만 사용자 쿠키 입력 후 확인이 남았다.

## 확정된 결정

| 항목 | 선택 |
|---|---|
| 로컬 LLM 런타임 | **Ollama** (OpenAI 호환 API, tool-calling 지원). 설치 모델: `qwen2.5:7b` |
| 챗봇 범위 (1차) | **조회부터 (Phase A, read-only)** — 이후 액션 확장 |
| Claude 연결 | **구독 쿠키 방식**(`CLAUDE_SESSION_KEY`, 추가 과금 없음) 우선, 없으면 공식 API(`ANTHROPIC_API_KEY`)로 폴백 |
| 쿠키/키 관리 | **백엔드 루트 `.env`** (프론트 노출 없음). `app/__init__.py`에서 `load_dotenv`로 로드 |
| 쿠키 모드 도구 처리 | **프롬프트 에뮬레이션(ReAct 루프)** — 웹 세션엔 네이티브 tool_use가 없어 JSON 액션 규약으로 대체 |

## 아키텍처

```
[Next.js 채팅 UI]  ──POST /chat (SSE 스트리밍)──▶  [FastAPI]
   모델 선택 ▼                                        ├─ 라우터: model = "claude" | "local"
   Claude / 로컬                                      ├─ ClaudeProvider  (anthropic SDK, ANTHROPIC_API_KEY)
                                                      ├─ LocalProvider   (Ollama /api/chat)
                                                      └─ 도구 실행기 ─▶ 기존 ERP 서비스 함수 직접 호출
```

**원칙**
1. LLM 호출·도구 실행은 전부 백엔드. 키는 서버 `.env`.
2. `Provider` 공통 인터페이스(`chat(messages, tools) -> 스트림`)로 Claude/로컬 교체.
3. 도구 스키마(JSON)는 한 번만 정의, 두 provider가 공유(포맷 차이는 어댑터가 변환).
4. 도구 = 기존 REST 로직 재사용 → 재고 반영·검증이 챗봇에서도 그대로 동작.

## Phase A 범위 (1차 구현 대상)

**도구 (read-only)**
- `get_dashboard()` — 매출·재고·미수/미지급 요약
- `get_inventory(query?)` — 품목·재고 조회 (품명/코드 필터)
- `list_orders(status?, type?)` — 주문 조회
- `list_partners(kind?)` — 거래처 조회

**대화 예시**
- "탄산수 재고 얼마야?" → `get_inventory("탄산수")`
- "안전재고 미달인 품목 알려줘" → `get_inventory` + 필터
- "이번 달 미수금은?" → `get_dashboard`

**엔드포인트**
- `POST /chat` — body: `{ model: "claude"|"local", messages: [...] }`, 응답: SSE 텍스트 스트림 + 도구 호출 이벤트

**환경변수 (루트 `.env`)**
```
# Claude 구독 쿠키 방식(우선) — claude.ai F12 > Application > Cookies
CLAUDE_SESSION_KEY=sk-ant-sid01-...
CLAUDE_ORG_ID=...
CLAUDE_CF_CLEARANCE=   # 선택(Cloudflare), 30분마다 만료
CLAUDE_CF_BM=          # 선택
# 공식 API 폴백
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-5
# 로컬 LLM
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
```

**구현 파일**
- `backend/app/chat/tools.py` — 도구 4종 정의·실행 + `tools_prompt()`(쿠키 모드용)
- `backend/app/chat/providers.py` — 라우팅: local / claude-쿠키 / claude-API 폴백
- `backend/app/chat/claude_cookie.py` — 쿠키 provider(대화 생성 → ReAct 루프 → SSE)
- `backend/app/chat/router.py` — `POST /chat` SSE 엔드포인트

## 이후 단계 (Phase B/C, 나중)

- **B. 액션**: `create_order`, `create_item` 등 write 도구 — 실행 전 사용자 확인 단계 필수.
- **C. 문서 도구**: `save_pdf`(주문서/재고표), `read_file`(CSV→품목 등록 등).

## 메모 / 리스크

- 로컬 LLM(Ollama)의 tool-calling은 Claude보다 불안정 → 복잡한 요청은 Claude, 단순 조회는 로컬로 라우팅하면 비용·품질 균형.
- Ollama는 별도 설치 필요(`brew install ollama` + `ollama pull qwen2.5`). docker-compose에 컨테이너로 넣을지, 호스트 설치를 쓸지는 구현 시 결정.
- 스트리밍은 FastAPI `StreamingResponse`(SSE) + 프론트 `EventSource`/fetch reader.
