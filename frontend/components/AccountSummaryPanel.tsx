export default function AccountSummaryPanel() {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-lg font-semibold text-white">Account Summary</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Workspace</div>
          <div className="mt-1 text-sm text-slate-200">Trade-X Paper Lab</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Region</div>
          <div className="mt-1 text-sm text-slate-200">US East</div>
        </div>
      </div>
    </section>
  );
}