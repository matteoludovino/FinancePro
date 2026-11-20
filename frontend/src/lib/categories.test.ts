import { describe, expect, it } from "vitest";
import { categoryLabel, categoryTree } from "./categories";
import type { Category } from "./types";

const c = (id: number, name: string, parent_id: number | null = null): Category => ({
  id,
  name,
  parent_id,
  type: "expense",
  slug: null,
  is_archived: false,
});

const categories = [c(1, "Transporte"), c(2, "Alimentação"), c(3, "Restaurantes", 2), c(4, "Mercado", 2)];

describe("categories", () => {
  it("labels a subcategory with its parent", () => {
    expect(categoryLabel(categories, 3)).toBe("Alimentação › Restaurantes");
    expect(categoryLabel(categories, 1)).toBe("Transporte");
    expect(categoryLabel(categories, null)).toBe("Sem categoria");
  });

  it("groups subcategories under their parent, in Portuguese alphabetical order", () => {
    expect(
      categoryTree(categories).map(({ parent, children }) => [parent.name, children.map((x) => x.name)]),
    ).toEqual([
      ["Alimentação", ["Mercado", "Restaurantes"]],
      ["Transporte", []],
    ]);
  });
});
