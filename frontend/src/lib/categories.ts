"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Category } from "./types";

export const CATEGORIES = ["categories"] as const;

export function useCategories() {
  return useQuery({ queryKey: CATEGORIES, queryFn: () => api.get<Category[]>("/categories") });
}

/** "Alimentação › Restaurantes", or the name alone for a top-level category. */
export function categoryLabel(categories: Category[], id: number | null): string {
  const category = categories.find((c) => c.id === id);
  if (!category) return "Sem categoria";
  const parent = categories.find((c) => c.id === category.parent_id);
  return parent ? `${parent.name} › ${category.name}` : category.name;
}

/** Top-level categories, each followed by its subcategories, alphabetically. */
export function categoryTree(categories: Category[]): { parent: Category; children: Category[] }[] {
  const byName = (a: Category, b: Category) => a.name.localeCompare(b.name, "pt-BR");
  return categories
    .filter((c) => c.parent_id === null)
    .sort(byName)
    .map((parent) => ({
      parent,
      children: categories.filter((c) => c.parent_id === parent.id).sort(byName),
    }));
}
