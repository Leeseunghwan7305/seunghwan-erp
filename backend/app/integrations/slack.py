"""웹훅 알림 전송(Slack / Discord 자동 감지). 전송은 부작용이라 반드시 사용자 확인 후에만 호출된다.

같은 SLACK_WEBHOOK_URL 변수에 Slack 또는 Discord Incoming Webhook URL을 넣을 수 있다.
- Slack : {"text": ...}
- Discord: {"content": ...}
URL 호스트로 형식을 자동 판별한다.
"""
import os

import httpx

from ..audit import record


def _target(url: str) -> tuple[str, dict]:
    """URL로 대상 서비스와 페이로드 형식을 정한다."""
    if "discord.com" in url or "discordapp.com" in url:
        return "discord", {}
    return "slack", {}


def send_message(text: str, actor: str | None = None) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "보낼 내용이 비었습니다."}
    url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        record("notify:send", "webhook 미설정", ok=False, actor=actor)
        return {"ok": False, "error": "SLACK_WEBHOOK_URL이 설정되지 않았습니다. 루트 .env에 넣고 백엔드를 재시작하세요."}

    service, _ = _target(url)
    payload = {"content": text} if service == "discord" else {"text": text}
    try:
        r = httpx.post(url, json=payload, timeout=15.0)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        record(f"{service}:send", f"{text[:80]} | 실패: {e}", ok=False, actor=actor)
        return {"ok": False, "error": f"{service} 전송 실패: {e}"}
    record(f"{service}:send", text[:200], ok=True, actor=actor)
    return {"ok": True, "message": f"{service}로 전송했습니다."}
