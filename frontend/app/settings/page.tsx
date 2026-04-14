import DashboardLayout from "@/components/DashboardLayout";
import PageHeader from "@/components/ui/PageHeader";
import AccountSummaryPanel from "@/components/AccountSummaryPanel";
import SettingsDeploymentCard from "@/components/SettingsDeploymentCard";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  return (
    <DashboardLayout>
      <PageHeader
        eyebrow="Workspace"
        title="Settings"
        description="Account details, saved preferences, and deployment info. Bot execution controls live on Portfolio; use Integration in the sidebar for API/bot/Ollama diagnostics."
      />
      <div className="mx-auto max-w-3xl space-y-8 px-4 py-6 sm:px-6 lg:px-8">
        <AccountSummaryPanel />
        <SettingsDeploymentCard />
      </div>
    </DashboardLayout>
  );
}
