import { AutoTradingPanel } from "@/components/temp";
import { DashboardLayout } from "@/components/DashboardLayout";
import { PortfolioPanel } from "@/components/PortfolioPanel";
import { PageHeader } from "@/components/ui/PageHeader";

export const dynamic = "force-dynamic";

export default function PortfolioPage() {
  return (
    <DashboardLayout>
      <PageHeader
        eyebrow="Paper account"
        title="Portfolio"
        description="Your simulated USDT balance, BTC positions, and manual paper orders. Below that, configure the AI bot: signal source, execution mode (signal-only → full auto on paper), cooldowns, and safety limits."
      />
      <main className="mx-auto max-w-5xl space-y-10 px-4 py-8 sm:px-6 lg:px-8">
        <PortfolioPanel />
        <AutoTradingPanel />
      </main>
    </DashboardLayout>
  );
}
