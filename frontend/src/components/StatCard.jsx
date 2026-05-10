export function StatCard({ label, value, detail }) {
  return (
    <section className="rounded-lg border border-line bg-panel px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-2 text-xl font-semibold text-slate-50">{value}</div>
      {detail ? <div className="mt-1 text-sm text-slate-400">{detail}</div> : null}
    </section>
  );
}
