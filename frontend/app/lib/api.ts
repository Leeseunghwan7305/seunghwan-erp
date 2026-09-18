const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const del = (path: string) => request<void>(path, { method: "DELETE" });
const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
const put = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });

// ---- Types ---------------------------------------------------------------

export interface DashboardSummary {
  item_count: number;
  partner_count: number;
  total_stock_qty: number;
  below_safety_count: number;
  sales_total: number;
  purchase_total: number;
  receivable: number;
  payable: number;
  open_orders: number;
}

export interface Item {
  id: number;
  code: string;
  name: string;
  unit: string;
  purchase_price: number;
  sale_price: number;
  safety_stock: number;
  quantity: number;
  below_safety: boolean;
}
export interface ItemCreate {
  code: string;
  name: string;
  unit: string;
  purchase_price: number;
  sale_price: number;
  safety_stock: number;
  initial_stock: number;
}
export interface ItemUpdate {
  name: string;
  unit: string;
  purchase_price: number;
  sale_price: number;
  safety_stock: number;
  quantity: number;
}

export interface Partner {
  id: number;
  name: string;
  kind: "supplier" | "customer";
  phone?: string | null;
  biz_no?: string | null;
}
export interface PartnerIn {
  name: string;
  kind: "supplier" | "customer";
  phone?: string | null;
  biz_no?: string | null;
}

export interface Employee {
  id: number;
  name: string;
  department?: string | null;
  position?: string | null;
  hire_date?: string | null;
  role_id?: number | null;
  role_name?: string | null;
}
export interface EmployeeIn {
  name: string;
  department?: string | null;
  position?: string | null;
  hire_date?: string | null;
  role_id?: number | null;
}

export interface Role {
  id: number;
  name: string;
  description?: string | null;
  permissions: string[];
}
export interface RoleIn {
  name: string;
  description?: string | null;
  permissions: string[];
}

export interface Account {
  id: number;
  code: string;
  name: string;
  category: string;
  entry_side: string;
  memo?: string | null;
}
export interface AccountIn {
  code: string;
  name: string;
  category: string;
  entry_side: string;
  memo?: string | null;
}

export interface Expense {
  id: number;
  expense_date: string;
  account: string;
  memo?: string | null;
  dept?: string | null;
  method: string;
  amount: number;
}
export interface ExpenseIn {
  expense_date: string;
  account: string;
  memo?: string | null;
  dept?: string | null;
  method: string;
  amount: number;
}

export interface OrderLineRead {
  item_id: number;
  item_name: string;
  quantity: number;
  unit_price: number;
  amount: number;
}
export interface Order {
  id: number;
  order_type: "purchase" | "sale";
  partner_id: number;
  partner_name: string;
  order_date: string;
  status: "draft" | "confirmed" | "done";
  total: number;
  lines: OrderLineRead[];
}
export interface OrderCreate {
  order_type: "purchase" | "sale";
  partner_id: number;
  lines: { item_id: number; quantity: number; unit_price?: number }[];
}

// ---- API -----------------------------------------------------------------

// ---- AI: RAG 지식 문서 ----------------------------------------------------

export type DocStatus = "indexing" | "ready" | "error";
export type DocSourceType = "paste" | "txt" | "md" | "pdf";

export interface RagDocument {
  id: number;
  title: string;
  source_type: DocSourceType;
  filename: string | null;
  char_count: number;
  chunk_count: number;
  status: DocStatus;
  error: string | null;
  created_at: string;
}

export interface RagSearchHit {
  document_id: number;
  title: string;
  ordinal: number;
  content: string;
  score: number;
}

export interface RagDocumentContent {
  id: number;
  title: string;
  chunk_count: number;
  content: string;
}

export interface RagManual {
  title: string | null; // 출처 문서 제목(없으면 매칭 실패)
  text: string; // 화면 섹션을 이어붙인 매뉴얼 본문
  score: number;
}

async function uploadRagDocument(form: FormData): Promise<RagDocument> {
  // multipart 업로드 — request()의 JSON 헤더를 쓰지 않는다.
  const res = await fetch(`${BASE}/rag/documents`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<RagDocument>;
}

export const api = {
  dashboard: () => request<DashboardSummary>("/dashboard"),

  items: () => request<Item[]>("/items"),
  createItem: (p: ItemCreate) => post<Item>("/items", p),
  updateItem: (id: number, p: ItemUpdate) => put<Item>(`/items/${id}`, p),
  deleteItem: (id: number) => del(`/items/${id}`),

  partners: () => request<Partner[]>("/partners"),
  createPartner: (p: PartnerIn) => post<Partner>("/partners", p),
  updatePartner: (id: number, p: PartnerIn) => put<Partner>(`/partners/${id}`, p),
  deletePartner: (id: number) => del(`/partners/${id}`),

  employees: () => request<Employee[]>("/employees"),
  createEmployee: (p: EmployeeIn) => post<Employee>("/employees", p),
  updateEmployee: (id: number, p: EmployeeIn) => put<Employee>(`/employees/${id}`, p),
  deleteEmployee: (id: number) => del(`/employees/${id}`),

  roles: () => request<Role[]>("/roles"),
  createRole: (p: RoleIn) => post<Role>("/roles", p),
  updateRole: (id: number, p: RoleIn) => put<Role>(`/roles/${id}`, p),
  deleteRole: (id: number) => del(`/roles/${id}`),

  accounts: () => request<Account[]>("/accounts"),
  createAccount: (p: AccountIn) => post<Account>("/accounts", p),
  updateAccount: (id: number, p: AccountIn) => put<Account>(`/accounts/${id}`, p),
  deleteAccount: (id: number) => del(`/accounts/${id}`),

  expenses: () => request<Expense[]>("/expenses"),
  createExpense: (p: ExpenseIn) => post<Expense>("/expenses", p),
  updateExpense: (id: number, p: ExpenseIn) => put<Expense>(`/expenses/${id}`, p),
  deleteExpense: (id: number) => del(`/expenses/${id}`),

  orders: () => request<Order[]>("/orders"),
  createOrder: (p: OrderCreate) => post<Order>("/orders", p),
  confirmOrder: (id: number) => post<Order>(`/orders/${id}/confirm`, {}),
  deleteOrder: (id: number) => del(`/orders/${id}`),

  ragDocuments: () => request<RagDocument[]>("/rag/documents"),
  createRagDocument: (form: FormData) => uploadRagDocument(form),
  deleteRagDocument: (id: number) => del(`/rag/documents/${id}`),
  ragDocumentContent: (id: number) =>
    request<RagDocumentContent>(`/rag/documents/${id}/content`),
  ragSearch: (query: string, top_k = 5) =>
    post<{ results: RagSearchHit[] }>("/rag/search", { query, top_k }),
  ragManual: (query: string) => post<RagManual>("/rag/manual", { query }),

  agentPlan: (instruction: string, screen?: string) =>
    post<AgentProposal>("/agent/plan", { instruction, screen }),
  agentApply: (proposal: AgentProposal) =>
    post<AgentApplyResult>("/agent/apply", { proposal }),
};

// ---- 실행(쓰기) 에이전트 --------------------------------------------------

export interface AgentProposal {
  ok: boolean;
  action?: "create" | "update";
  entity?: string;
  entity_label?: string;
  values?: Record<string, unknown>;
  target?: { code?: string; id?: number } | null;
  summary?: string;
  warnings?: string[];
  error?: string;
}
export interface AgentApplyResult {
  ok: boolean;
  message?: string;
  id?: number;
  error?: string;
}

// ₩(U+20A9)는 mono subset에 없어 폴백 글리프와 첫 숫자가 겹친다 → 얇은 공백으로 분리.
export const won = (n: number) => `₩ ${n.toLocaleString("ko-KR")}`;

export const statusLabel: Record<Order["status"], string> = {
  draft: "작성",
  confirmed: "확정",
  done: "완료",
};
