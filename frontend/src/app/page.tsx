import Link from "next/link";
import { DemoButton } from "@/components/demo-button";
import { DEMO_MODE } from "@/lib/demo";

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center gap-6 p-6">
      <p className="text-sm font-semibold text-emerald-700">FinancePro</p>
      <h1 className="text-4xl font-semibold tracking-tight text-zinc-900">
        Seu extrato vira um retrato claro de para onde vai o seu dinheiro.
      </h1>
      <p className="text-lg text-zinc-600">
        Importe o CSV do banco, deixe os gastos categorizados e acompanhe o orçamento do mês, com o cartão de
        crédito e as parcelas contados do jeito certo.
      </p>
      {DEMO_MODE ? (
        <div className="space-y-3">
          <DemoButton className="px-5 py-2.5" />
          <p className="text-sm text-zinc-500">
            Uma cópia só sua, com seis meses de extratos fictícios de conta e cartão. Sem cadastro; apagada
            depois de 3 horas sem uso.
          </p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          <Link
            href="/criar-conta"
            className="rounded-lg bg-emerald-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-800"
          >
            Criar conta grátis
          </Link>
          <Link
            href="/entrar"
            className="rounded-lg border border-zinc-300 bg-white px-5 py-2.5 text-sm font-medium text-zinc-800 hover:bg-zinc-50"
          >
            Entrar
          </Link>
        </div>
      )}
    </main>
  );
}
