export default function Home() {
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl space-y-8">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8">
          <div className="text-xs uppercase tracking-[0.2em] text-cyan-400">Trade-X</div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Welcome to Trade-X 🚀
          </h1>
          <p className="mt-3 max-w-2xl text-sm text-slate-300">
            Modern crypto paper-trading dashboard for BTC/USDT monitoring, portfolio tracking, and
            bot controls.
          </p>
        </section>
        <section className="grid gap-4 sm:grid-cols-3">
          <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Market</div>
            <div className="mt-2 text-xl font-semibold text-white">BTC/USDT</div>
          </article>
          <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Paper Equity</div>
            <div className="mt-2 text-xl font-semibold text-emerald-300">$10,482.17</div>
          </article>
          <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="text-xs uppercase tracking-[0.15em] text-slate-400">Bot Status</div>
            <div className="mt-2 text-xl font-semibold text-cyan-300">Running</div>
          </article>
        </section>
      </div>
    </main>
  );
}
