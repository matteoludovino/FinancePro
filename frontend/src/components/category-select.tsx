"use client";

import type { ComponentProps } from "react";
import { Select } from "@/components/ui";
import { categoryTree } from "@/lib/categories";
import type { Category } from "@/lib/types";

/** Categories grouped by parent; archived ones are left out unless already chosen. */
export function CategorySelect({
  categories,
  value,
  ...props
}: Omit<ComponentProps<"select">, "children"> & { categories: Category[] }) {
  const visible = categories.filter((c) => !c.is_archived || String(c.id) === String(value));
  return (
    <Select value={value} {...props}>
      <option value="">Escolha…</option>
      {(["expense", "income"] as const).map((type) =>
        categoryTree(visible.filter((c) => c.type === type)).map(({ parent, children }) => (
          <optgroup key={parent.id} label={`${type === "expense" ? "Gasto" : "Receita"} · ${parent.name}`}>
            <option value={parent.id}>{parent.name}</option>
            {children.map((child) => (
              <option key={child.id} value={child.id}>
                {parent.name} › {child.name}
              </option>
            ))}
          </optgroup>
        )),
      )}
    </Select>
  );
}
