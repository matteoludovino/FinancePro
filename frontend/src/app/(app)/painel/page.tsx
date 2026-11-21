import { Suspense } from "react";
import { Loading } from "@/components/ui";
import { Dashboard } from "./dashboard";

// Starts on the current month, read from the visitor's clock: kept out of the prerendered shell.
export default function DashboardPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Dashboard />
    </Suspense>
  );
}
