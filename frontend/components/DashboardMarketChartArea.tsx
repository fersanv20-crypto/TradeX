export default function DashboardMarketChartArea() {
  return (
    <section className="mx-auto mt-6 w-full max-w-6xl px-4 sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">BTC / USDT</h3>
          <div className="text-sm text-emerald-300">67,482.10 (+1.7%)</div>
        </div>
        <div className="mt-4 grid h-72 place-items-center rounded-xl border border-dashed border-slate-700 bg-slate-950/70 text-sm text-slate-400">
          Chart area placeholder (candles, indicators, depth)
        </div>
      </div>
    </section>
  );
}