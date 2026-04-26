export default function DashboardBotBar() {
  return (
    <section className="mx-auto mt-6 w-full max-w-6xl px-4 sm:px-6 lg:px-8">
      <div className="grid gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:grid-cols-3">
        <div>
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Signal Source</div>
          <div className="mt-1 text-sm font-medium text-white">Hybrid (Trend + Momentum)</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Execution Mode</div>
          <div className="mt-1 text-sm font-medium text-cyan-300">Paper Auto</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Cooldown</div>
          <div className="mt-1 text-sm font-medium text-white">90 seconds</div>
        </div>
      </div>
    </section>
  );
}