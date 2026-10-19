"use client";

import { useRef, useState } from "react";
import PageHeader from "../../components/PageHeader";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const EXAMPLES = ["빨간 음료 캔", "녹색 유리병", "노란 상자", "파란 캔"];

interface Hit {
  id: number;
  filename: string;
  label: string;
  is_sample: boolean;
  score: number;
}

export default function ImageSearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [mode, setMode] = useState<"" | "text" | "image">("");
  const [queryPreview, setQueryPreview] = useState<string>(""); // 이미지 검색 시 올린 쿼리 이미지
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const searchFileRef = useRef<HTMLInputElement>(null);
  const addFileRef = useRef<HTMLInputElement>(null);

  const searchText = async (text: string) => {
    const query = text.trim();
    if (!query || busy) return;
    setBusy(true);
    setError("");
    setMode("text");
    setQueryPreview("");
    try {
      const res = await fetch(`${BASE}/rag/image/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: 8 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `서버 오류 (${res.status})`);
      setHits(data.results ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const searchByImage = async (file: File) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setMode("image");
    setQueryPreview(URL.createObjectURL(file));
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("top_k", "8");
      const res = await fetch(`${BASE}/rag/image/search-by-image`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `서버 오류 (${res.status})`);
      setHits(data.results ?? []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const addImage = async (file: File) => {
    setBusy(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("label", file.name.replace(/\.[^.]+$/, ""));
      const res = await fetch(`${BASE}/rag/image/upload`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `서버 오류 (${res.status})`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="AI · CLIP Image Search"
        title="이미지 의미 검색"
        desc="이미지와 텍스트를 같은 임베딩 공간(CLIP)에 넣어, 말로 이미지를 찾거나 이미지로 비슷한 이미지를 찾습니다. 색·형태의 의미를 이해하는 멀티모달 검색입니다."
      />

      <div className="rounded-card border border-line bg-surface p-5">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            searchText(q);
          }}
          className="flex gap-2"
        >
          <input
            className="flex-1 rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-ink-3 focus:border-brand focus:outline-none"
            placeholder="예) 빨간 음료 캔"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            disabled={busy}
          />
          <button
            type="submit"
            disabled={busy || !q.trim()}
            className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {busy && mode === "text" ? "검색 중…" : "텍스트 검색"}
          </button>
          <button
            type="button"
            onClick={() => searchFileRef.current?.click()}
            disabled={busy}
            className="rounded-lg border border-line px-4 py-3 text-sm font-medium text-ink-2 transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
          >
            이미지로 검색
          </button>
          <input
            ref={searchFileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) searchByImage(f);
              e.target.value = "";
            }}
          />
        </form>
        {!busy && hits.length === 0 && mode === "" && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {EXAMPLES.map((g) => (
              <button
                key={g}
                onClick={() => {
                  setQ(g);
                  searchText(g);
                }}
                className="rounded-full border border-line bg-surface px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-brand hover:text-brand"
              >
                {g}
              </button>
            ))}
            <button
              onClick={() => addFileRef.current?.click()}
              className="ml-auto text-xs text-ink-3 underline-offset-2 hover:text-brand hover:underline"
            >
              + 내 이미지 추가
            </button>
            <input
              ref={addFileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) addImage(f);
                e.target.value = "";
              }}
            />
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-card border border-danger/40 bg-danger-tint p-4 text-sm text-danger">
          ⚠️ {error}
        </div>
      )}

      {mode === "image" && queryPreview && (
        <div className="flex items-center gap-3 rounded-card border border-line bg-surface p-4">
          <span className="text-xs text-ink-3">쿼리 이미지</span>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={queryPreview} alt="쿼리 이미지" className="h-16 w-16 rounded-md border border-line object-cover" />
        </div>
      )}

      {hits.length > 0 && (
        <div className="rounded-card border border-line bg-surface p-5">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-mono text-sm font-semibold text-ink">유사 이미지</span>
            <span className="font-mono text-xs text-ink-2">{hits.length}개 · 유사도순</span>
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
            {hits.map((h) => (
              <div key={h.id} className="flex flex-col gap-2 rounded-lg border border-line p-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${BASE}/rag/image/${h.id}/file`}
                  alt={h.label}
                  className="aspect-square w-full rounded-md object-cover"
                />
                <div className="flex items-center justify-between px-1">
                  <span className="truncate text-xs text-ink">{h.label || `#${h.id}`}</span>
                  <span className="font-mono text-xs tabular-nums text-brand-strong">{h.score.toFixed(3)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-ink-3">
        * 샘플은 외부 저작권 없이 PIL로 합성한 제품 이미지입니다. CLIP이 색·형태 의미를 이해하므로 "빨간 캔"·"녹색 병" 같은 말로도,
        이미지를 올려서도 찾을 수 있습니다. torch는 선택적 의존성(`requirements-ml.txt`)입니다.
      </p>
    </div>
  );
}
