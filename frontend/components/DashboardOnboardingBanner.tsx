export default function DashboardOnboardingBanner() {
  return (
    <section className="mx-auto mt-6 w-full max-w-6xl px-4 sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-cyan-500/20 bg-gradient-to-r from-cyan-500/15 via-blue-500/10 to-slate-900 px-5 py-4">
        <h2 className="text-sm font-semibold text-white">Welcome back, trader</h2>
        <p className="mt-1 text-sm text-slate-300">
          Signals are active for BTC/USDT in paper mode. Review bot limits before enabling full
          auto execution.
        </p>
      </div>
    </section>
  );
}