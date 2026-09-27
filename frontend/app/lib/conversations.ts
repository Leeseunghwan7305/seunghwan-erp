// 2단계: 여러 대화를 localStorage에 저장하는 스토어.
// TanStack Query가 이 함수들을 감싸(queryFn/mutationFn) 목록 캐시·무효화를 관리한다.

export type Role = "user" | "assistant";
export interface Msg {
  role: Role;
  content: string;
  tools?: string[];
}
export interface Conversation {
  id: string;
  title: string;
  model: "claude" | "local";
  messages: Msg[];
  updatedAt: number;
}

const KEY = "erp_chats_v1";

function readAll(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as Conversation[]) : [];
    return Array.isArray(list) ? list.sort((a, b) => b.updatedAt - a.updatedAt) : [];
  } catch {
    return [];
  }
}

function writeAll(list: Conversation[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch {
    /* 용량 초과 등 무시 */
  }
}

// 충돌 없는 id (Date.now + 난수). crypto 있으면 사용.
function newId(): string {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch {
    /* ignore */
  }
  return `c_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
}

export function listConversations(): Conversation[] {
  return readAll();
}

export function getConversation(id: string | null): Conversation | null {
  if (!id) return null;
  return readAll().find((c) => c.id === id) ?? null;
}

export function createConversation(model: "claude" | "local" = "claude"): Conversation {
  const conv: Conversation = {
    id: newId(),
    title: "새 대화",
    model,
    messages: [],
    updatedAt: Date.now(),
  };
  writeAll([conv, ...readAll()]);
  return conv;
}

// 메시지·모델 갱신(제목은 첫 사용자 발화로 자동 지정).
export function saveConversation(
  id: string,
  patch: { messages?: Msg[]; model?: "claude" | "local" }
): Conversation | null {
  const list = readAll();
  const idx = list.findIndex((c) => c.id === id);
  if (idx < 0) return null;
  const cur = list[idx];
  const messages = patch.messages ?? cur.messages;
  const firstUser = messages.find((m) => m.role === "user")?.content;
  const next: Conversation = {
    ...cur,
    messages,
    model: patch.model ?? cur.model,
    title: cur.title === "새 대화" && firstUser ? firstUser.slice(0, 40) : cur.title,
    updatedAt: Date.now(),
  };
  list[idx] = next;
  writeAll(list);
  return next;
}

export function deleteConversation(id: string) {
  writeAll(readAll().filter((c) => c.id !== id));
}
