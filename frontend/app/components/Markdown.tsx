"use client";

import React from "react";

/**
 * 의존성 없는 초경량 Markdown 렌더러 (LLM 답변용 최소 문법).
 *
 * - HTML 문자열을 주입하지 않고 React 엘리먼트로 만들어 XSS를 원천 차단한다.
 * - 스트리밍 중 불완전한 마크다운(닫히지 않은 **, ``` 등)에도 관대하게 폴백한다.
 * - 지원: 제목(#~###), 굵게(**), 기울임(*), 인라인 코드(`), 코드블록(```),
 *   순서/비순서 목록, 링크([t](url)), 문단·줄바꿈.
 */

// 링크는 http(s)·상대경로만 허용(javascript: 등 차단).
const SAFE_HREF = /^(https?:\/\/|\/)/i;

function renderInline(text: string, keyBase: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*\n]+\*|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    const k = `${keyBase}-${i++}`;
    if (tok.startsWith("`")) {
      out.push(
        <code key={k} className="rounded bg-ink/10 px-1 py-0.5 font-mono text-[0.85em]">
          {tok.slice(1, -1)}
        </code>
      );
    } else if (tok.startsWith("**")) {
      out.push(<strong key={k}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith("*")) {
      out.push(<em key={k}>{tok.slice(1, -1)}</em>);
    } else {
      const mm = /\[([^\]]+)\]\(([^)]+)\)/.exec(tok);
      if (mm && SAFE_HREF.test(mm[2])) {
        out.push(
          <a
            key={k}
            href={mm[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand underline underline-offset-2 hover:text-brand-strong"
          >
            {mm[1]}
          </a>
        );
      } else {
        out.push(tok); // 안전하지 않거나 파싱 실패 시 원문 그대로
      }
    }
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export default function Markdown({ text }: { text: string }) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // 코드블록 ```
    if (line.trim().startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        buf.push(lines[i]);
        i++;
      }
      i++; // 닫는 펜스 소비(없으면 그냥 끝)
      blocks.push(
        <pre
          key={key++}
          className="overflow-x-auto rounded-lg bg-ink/5 p-3 font-mono text-xs leading-relaxed"
        >
          <code>{buf.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // 제목 #~###
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) {
      const lvl = h[1].length;
      blocks.push(
        React.createElement(
          `h${lvl + 2}`,
          { key: key++, className: "font-semibold text-[1.05em]" },
          renderInline(h[2], `h${key}`)
        )
      );
      i++;
      continue;
    }

    // 비순서 목록
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="list-disc space-y-1 pl-5">
          {items.map((it, j) => (
            <li key={j}>{renderInline(it, `ul${key}-${j}`)}</li>
          ))}
        </ul>
      );
      continue;
    }

    // 순서 목록
    if (/^\s*\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ""));
        i++;
      }
      blocks.push(
        <ol key={key++} className="list-decimal space-y-1 pl-5">
          {items.map((it, j) => (
            <li key={j}>{renderInline(it, `ol${key}-${j}`)}</li>
          ))}
        </ol>
      );
      continue;
    }

    // 빈 줄
    if (line.trim() === "") {
      i++;
      continue;
    }

    // 문단(연속된 일반 줄을 모아 <br/>로 잇는다)
    const para: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i]) &&
      !/^#{1,3}\s+/.test(lines[i]) &&
      !lines[i].trim().startsWith("```")
    ) {
      para.push(lines[i]);
      i++;
    }
    blocks.push(
      <p key={key++}>
        {para.map((pl, j) => (
          <React.Fragment key={j}>
            {j > 0 && <br />}
            {renderInline(pl, `p${key}-${j}`)}
          </React.Fragment>
        ))}
      </p>
    );
  }

  return <div className="space-y-2">{blocks}</div>;
}
