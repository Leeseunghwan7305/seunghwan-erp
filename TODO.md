# 오늘 할 일 (2026-09-16)

> ✅ 구현 완료 (2026-09-16). Claude 쿠키 경로만 사용자 쿠키 입력 후 실동작 확인 필요.

## 1. Claude 구독 연결 — ✅ 구현 완료
- **구독 쿠키 방식** 채택: claude.ai 세션 쿠키(`CLAUDE_SESSION_KEY`)로 내부 API 호출 (추가 과금 없음).
  - `CLAUDE_SESSION_KEY`가 없으면 공식 API(`ANTHROPIC_API_KEY`, 사용량 과금)로 자동 폴백.
- 백엔드 `backend/app/chat/claude_cookie.py`, 키/쿠키는 루트 `.env` 관리.
- ⚠️ 남은 것: 사용자가 `.env`에 실제 쿠키를 넣고 claude.ai 실호출 검증 (내가 못 하는 부분).

## 2. 모델 라우팅 (Claude ↔ 로컬 LLM 선택) — ✅ 구현·검증 완료
- `POST /chat`의 `model: "claude"|"local"` 로 라우팅. 프론트 토글 UI 존재.
- 로컬(Ollama qwen2.5:7b) 경로 end-to-end 검증 완료.

## 3. 도구(툴) 여러 개 만들어보기 — ✅ Phase A 완료 (조회 전용)
- 구현됨: `get_dashboard`, `get_inventory`, `list_orders`, `list_partners` (기존 ERP 데이터 재사용).
- 로컬 LLM에서 도구 호출 동작 검증 완료. 쿠키 Claude는 프롬프트 기반 도구 에뮬레이션으로 동일 도구 재사용.
- ✅ 후속(RAG): 지식 문서(파일/PDF/텍스트) 업로드·색인·검색 + 챗 도구(`search_documents`) 연동 완료 (2026-09-16). 설계: `docs/superpowers/specs/2026-09-16-rag-knowledge-docs-design.md`.

---

## 설계 메모
- 위 3개 항목은 **AI 챗봇 하나로 통합**하기로 함 → 상세 설계: [`docs/ai-chatbot-plan.md`](./docs/ai-chatbot-plan.md)
- 확정: 로컬 LLM = **Ollama**, 1차 범위 = **조회(Phase A)**, 키 관리 = **백엔드 .env**

---
*상태: Phase A 구현·검증 완료 (2026-09-16). Claude 쿠키 실호출은 사용자 쿠키 입력 후 확인.*
