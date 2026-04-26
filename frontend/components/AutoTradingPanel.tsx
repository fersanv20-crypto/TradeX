export default function AutoTradingPanel() {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <h2 className="text-lg font-semibold text-white">Auto Trading Controls</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Mode</div>
          <div className="mt-1 text-sm font-medium text-cyan-300">Signal + Auto Execution</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Max Position Size</div>
          <div className="mt-1 text-sm font-medium text-white">10% equity</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Stop Loss</div>
          <div className="mt-1 text-sm font-medium text-white">1.2%</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Status</div>
          <div className="mt-1 text-sm font-medium text-emerald-300">Active (Paper)</div>
        </div>
      </div>
    </section>
  );
}