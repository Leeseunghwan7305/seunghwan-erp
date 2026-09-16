import { ReactNode } from "react";

export type Column = {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
};

export default function DataTable({
  columns,
  rows,
}: {
  columns: Column[];
  rows: Record<string, ReactNode>[];
}) {
  const alignCls = (a?: Column["align"]) =>
    a === "right" ? "text-right" : a === "center" ? "text-center" : "text-left";
  // 우측 정렬 열은 대개 숫자 — 고정폭 tabular 로 자릿수 정렬.
  const numCls = (a?: Column["align"]) => (a === "right" ? "num" : "");

  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-2">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`whitespace-nowrap px-4 py-3 font-mono text-[11px] font-medium tracking-wide text-ink-3 ${alignCls(
                    c.align
                  )}`}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={i}
                className="border-b border-line text-ink transition-colors last:border-0 hover:bg-surface-2"
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`whitespace-nowrap px-4 py-3 ${alignCls(
                      c.align
                    )} ${numCls(c.align)}`}
                  >
                    {r[c.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
