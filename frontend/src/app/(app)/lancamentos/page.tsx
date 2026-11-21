import { Suspense } from "react";
import { Loading } from "@/components/ui";
import { TransactionsView } from "./transactions-view";

// The view starts on the current month, read from the visitor's clock. Cache Components prerender client
// components too; the boundary keeps that read out of the static shell, so it happens on each visit.
export default function TransactionsPage() {
  return (
    <Suspense fallback={<Loading />}>
      <TransactionsView />
    </Suspense>
  );
}
