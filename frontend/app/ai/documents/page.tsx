"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PageHeader from "../../components/PageHeader";
import Badge from "../../components/Badge";
import { api, RagDocument, RagSearchHit, DocStatus, DocSourceType } from "../../lib/api";

const STATUS: Record<DocStatus, { label: string; tone: "amber" | "green" | "red" }> = {
  indexing: { label: "색인 중", tone: "amber" },
  ready: { label: "준비됨", tone: "green" },
  error: { label: "오류", tone: "red" },
};

const SOURCE_LABEL: Record<DocSourceType, string> = {
  paste: "붙여넣기",
  txt: "TXT",
  md: "MD",
  pdf: "PDF",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [loadErr, setLoadErr] = useState("");

  const load = useCallback(async () => {
    try {
      setDocs(await api.ragDocuments());
      setLoadErr("");
    } catch (e) {
      setLoadErr((e as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // 색인 중 문서가 있으면 3초마다 폴링, 전부 끝나면 중단.
  useEffect(() => {
    if (!docs.some((d) => d.status === "indexing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs, load]);

  return (
    <div>
      <PageHeader
        eyebrow="AI · Knowledge"
        title="지식 문서"
        desc="문서를 올리면 임베딩으로 색인되어, AI 어시스턴트가 답변 근거로 검색해 씁니다."
        meta={
          <>
            총 <span className="num text-ink">{docs.length}</span>개
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <AddDocument onAdded={load} />
        <SearchTest />
      </div>

      <div className="mt-6">
        <p className="eyebrow mb-3">등록된 문서</p>
        {loadErr && (
          <p className="mb-3 rounded-lg border border-[#e6c3bd] bg-danger-tint px-4 py-2 text-sm text-danger">
            목록을 불러오지 못했습니다: {loadErr}
          </p>
        )}
        <DocumentTable docs={docs} onChanged={load} />
      </div>
    </div>
  );
}

// ---- 문서 추가 -------------------------------------------------------------

function AddDocument({ onAdded }: { onAdded: () => void }) {
  const [mode, setMode] = useState<"paste" | "file">("paste");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setTitle("");
    setText("");
    setFile(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    if (!title.trim()) return setErr("제목을 입력하세요.");
    if (mode === "paste" && !text.trim()) return setErr("내용을 입력하세요.");
    if (mode === "file" && !file) return setErr("파일을 선택하세요.");

    const form = new FormData();
    form.append("title", title.trim());
    if (mode === "paste") form.append("text", text);
    else if (file) form.append("file", file);

    setBusy(true);
    try {
      await api.createRagDocument(form);
      reset();
      onAdded();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      onSubmit={submit}
      className="rounded-card border border-line bg-surface p-5"
    >
      <p className="eyebrow mb-3">문서 추가</p>

      {/* 입력 방식 토글 */}
      <div className="mb-4 inline-flex overflow-hidden rounded-md border border-line text-sm">
        {(["paste", "file"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`px-4 py-1.5 transition-colors ${
              mode === m
                ? "bg-brand text-white"
                : "bg-surface text-ink-2 hover:text-ink"
            }`}
          >
            {m === "paste" ? "텍스트 붙여넣기" : "파일 업로드"}
          </button>
        ))}
      </div>

      <label className="mb-1 block text-sm text-ink-2">제목</label>
      <input
        className="mb-4 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
        placeholder="예) 출장비 규정"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      {mode === "paste" ? (
        <textarea
          className="h-40 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
          placeholder="문서 내용을 붙여넣으세요."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      ) : (
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.md,.markdown,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-ink-2 file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-brand-strong"
          />
          <p className="mt-2 text-[12px] text-ink-3">.txt · .md · .pdf 지원</p>
        </div>
      )}

      {err && <p className="mt-3 text-sm text-danger">{err}</p>}

      <button
        type="submit"
        disabled={busy}
        className="mt-4 rounded-lg bg-brand px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
      >
        {busy ? "등록 중…" : "등록"}
      </button>
    </form>
  );
}

// ---- 검색 테스트 -----------------------------------------------------------

function SearchTest() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<RagSearchHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || busy) return;
    setBusy(true);
    setErr("");
    try {
      const { results } = await api.ragSearch(query.trim());
      setHits(results);
    } catch (e) {
      setErr((e as Error).message);
      setHits(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-card border border-line bg-surface p-5">
      <p className="eyebrow mb-3">검색 테스트</p>
      <form onSubmit={run} className="flex gap-2">
        <input
          className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
          placeholder="예) 해외 출장 숙박비 한도"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button
          type="submit"
          disabled={busy || !query.trim()}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
        >
          검색
        </button>
      </form>

      {err && <p className="mt-3 text-sm text-danger">{err}</p>}

      <div className="mt-4 space-y-3">
        {hits && hits.length === 0 && (
          <p className="text-sm text-ink-3">일치하는 문서가 없습니다.</p>
        )}
        {hits?.map((h, i) => (
          <div key={i} className="rounded-lg border border-line bg-surface-2 p-3">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-ink">{h.title}</span>
              <span className="num text-[12px] text-brand-strong">
                유사도 {h.score.toFixed(3)}
              </span>
            </div>
            <p className="line-clamp-3 whitespace-pre-wrap text-[13px] leading-relaxed text-ink-2">
              {h.content}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- 문서 목록 -------------------------------------------------------------

function DocumentTable({
  docs,
  onChanged,
}: {
  docs: RagDocument[];
  onChanged: () => void;
}) {
  const [deleting, setDeleting] = useState<number | null>(null);

  const remove = async (d: RagDocument) => {
    if (!confirm(`"${d.title}" 문서를 삭제할까요?`)) return;
    setDeleting(d.id);
    try {
      await api.deleteRagDocument(d.id);
      onChanged();
    } catch (e) {
      alert(`삭제 실패: ${(e as Error).message}`);
    } finally {
      setDeleting(null);
    }
  };

  if (docs.length === 0) {
    return (
      <div className="rounded-card border border-dashed border-line-strong bg-surface p-10 text-center text-sm text-ink-3">
        아직 등록된 문서가 없습니다. 위에서 문서를 추가하세요.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-2">
              {["제목", "형식", "청크", "글자수", "상태", "등록일", ""].map((h, i) => (
                <th
                  key={i}
                  className={`whitespace-nowrap px-4 py-3 font-mono text-[11px] font-medium tracking-wide text-ink-3 ${
                    i === 2 || i === 3 ? "text-right" : i === 4 ? "text-center" : "text-left"
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => {
              const s = STATUS[d.status];
              return (
                <tr
                  key={d.id}
                  className="border-b border-line text-ink transition-colors last:border-0 hover:bg-surface-2"
                >
                  <td className="px-4 py-3">
                    <span className="font-medium">{d.title}</span>
                    {d.status === "error" && d.error && (
                      <span className="mt-0.5 block text-[12px] text-danger">{d.error}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-ink-2">{SOURCE_LABEL[d.source_type]}</td>
                  <td className="num px-4 py-3 text-right text-ink-2">{d.chunk_count}</td>
                  <td className="num px-4 py-3 text-right text-ink-2">
                    {d.char_count.toLocaleString("ko-KR")}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge tone={s.tone}>{s.label}</Badge>
                  </td>
                  <td className="num px-4 py-3 text-ink-3">{d.created_at.slice(0, 10)}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => remove(d)}
                      disabled={deleting === d.id}
                      className="text-[13px] text-ink-3 transition-colors hover:text-danger disabled:opacity-50"
                    >
                      {deleting === d.id ? "삭제 중…" : "삭제"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
