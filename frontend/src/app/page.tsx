import { ApiStatus } from "./api-status";

// Placeholder home for the scaffold: proves the /api rewrite reaches FastAPI.
export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col justify-center gap-3 p-6">
      <h1 className="text-3xl font-semibold tracking-tight">FinancePro</h1>
      <p className="text-zinc-600">Importe o extrato, categorize os gastos e acompanhe o orçamento.</p>
      <ApiStatus />
    </main>
  );
}
