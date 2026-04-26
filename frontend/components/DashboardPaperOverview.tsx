export default function DashboardPaperOverview() {
  return (
    <section className="mx-auto my-6 w-full max-w-6xl px-4 sm:px-6 lg:px-8">
      <div className="grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:grid-cols-2">
        <article className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Active Position</div>
          <div className="mt-2 text-lg font-semibold text-white">0.142 BTC Long</div>
          <div className="text-sm text-slate-300">Entry: 66,920.15</div>
        </article>
        <article className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Session PnL</div>
          <div className="mt-2 text-lg font-semibold text-emerald-300">+$248.30</div>
          <div className="text-sm text-slate-300">After fees and slippage</div>
        </article>
      </div>
    </section>
  );
}