import { DashboardAtAGlance } from "@/components/DashboardAtAGlance";
import { DashboardBotBar } from "@/components/DashboardBotBar";
import { DashboardMarketChartArea } from "@/components/DashboardMarketChartArea";
import { DashboardOnboardingBanner } from "@/components/DashboardOnboardingBanner";
import { DashboardPaperOverview } from "@/components/DashboardPaperOverview";
import { DashboardLayout } from "@/components/DashboardLayout";
import { PaperEquityBar } from "@/components/PaperEquityBar";
import { PageHeader } from "@/components/ui/PageHeader";

/** Auth + client charts: avoid static prerender edge cases in CI / Windows builds. */
export const dynamic = "force-dynamic";

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="flex min-h-0 flex-1 flex-col">
        <PageHeader
          eyebrow="Dashboard"
          title="BTC / USDT · Paper mode"
          description="Live chart, indicators, and market context with simulated execution. Portfolio holds orders, bot modes, and safety limits; use the assistant for explanations."
          action={
            <div className="w-full max-w-sm sm:w-72">
              <PaperEquityBar />
            </div>
          }
        />
        <DashboardOnboardingBanner />
        <DashboardAtAGlance />
        <DashboardBotBar />
        <div className="flex min-h-0 flex-1 flex-col lg:min-h-[calc(100dvh-12rem)]">
          <DashboardMarketChartArea />
        </div>
        <DashboardPaperOverview />
      </div>
    </DashboardLayout>
  );
}
