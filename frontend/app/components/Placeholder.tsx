import PageHeader from "./PageHeader";

export default function Placeholder({
  title,
  desc,
}: {
  title: string;
  desc?: string;
}) {
  return (
    <div>
      <PageHeader eyebrow="준비 중" title={title} desc={desc} />
      <div className="rounded-card border border-dashed border-line-strong bg-surface px-6 py-16 text-center">
        <div className="eyebrow mb-3">WIP</div>
        <div className="text-sm text-ink-2">
          이 화면은 아직 준비 중입니다.
        </div>
      </div>
    </div>
  );
}
