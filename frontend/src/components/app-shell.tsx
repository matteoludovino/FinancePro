"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useLogout, useMe } from "@/lib/session";

const NAV = [
  { href: "/painel", label: "Painel" },
  { href: "/contas", label: "Contas" },
  { href: "/categorias", label: "Categorias" },
  { href: "/regras", label: "Regras" },
  { href: "/configuracoes", label: "Configurações" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const logout = useLogout();

  useEffect(() => {
    if (me.data === null) router.replace(`/entrar?next=${encodeURIComponent(pathname)}`);
  }, [me.data, pathname, router]);

  return (
    <div className="flex flex-1 flex-col md:flex-row">
      <aside className="border-b border-zinc-200 bg-white md:sticky md:top-0 md:flex md:h-screen md:w-56 md:flex-col md:border-r md:border-b-0">
        <div className="flex items-center justify-between gap-4 p-4 md:block">
          <Link href="/painel" className="text-lg font-semibold text-emerald-700">
            FinancePro
          </Link>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="text-sm text-zinc-600 hover:text-zinc-900 md:hidden"
          >
            Sair
          </button>
        </div>
        <nav aria-label="Principal" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:pb-0">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm whitespace-nowrap ${
                  active ? "bg-emerald-50 font-medium text-emerald-800" : "text-zinc-700 hover:bg-zinc-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto hidden border-t border-zinc-200 p-4 md:block">
          {/* The page renders right away; who is signed in fills in when /auth/me answers. */}
          <p className="truncate text-sm font-medium text-zinc-900">{me.data?.name ?? "\u00a0"}</p>
          <p className="truncate text-xs text-zinc-500">{me.data?.email ?? "\u00a0"}</p>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="mt-3 text-sm text-zinc-600 hover:text-zinc-900"
          >
            Sair
          </button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}
