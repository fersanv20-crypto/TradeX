import DashboardLayout from "@/components/DashboardLayout";
import BacktestRunner from "@/components/BacktestRunner";
import PageHeader from "@/components/ui/PageHeader";

export const dynamic = "force-dynamic";

export default function BacktestPage() {
  return (
    <DashboardLayout>
      <PageHeader
        eyebrow="Strategy evaluation"
        title="Backtesting"
        description="Replay the same signal stack used on the dashboard against historical candles. Tune interval, dates, signal source, and execution mode — results are simulated and may take a short while for long ranges."
      />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <BacktestRunner />
      </main>
    </DashboardLayout>
  );
}
