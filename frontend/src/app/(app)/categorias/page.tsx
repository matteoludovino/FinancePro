"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Dialog,
  Field,
  formValues,
  Input,
  Loading,
  PageHeader,
} from "@/components/ui";
import { api, errorMessage, fieldError } from "@/lib/api";
import { CATEGORIES, categoryTree, useCategories } from "@/lib/categories";
import type { Category, CategoryType } from "@/lib/types";

type Editing =
  { mode: "new"; type: CategoryType; parent: Category | null } | { mode: "edit"; category: Category };

export default function CategoriesPage() {
  const categories = useCategories();
  const [editing, setEditing] = useState<Editing | null>(null);
  return (
    <>
      <PageHeader
        title="Categorias"
        description="Renomeie, crie ou arquive à vontade. Categorias arquivadas somem das escolhas, mas o histórico fica."
      />
      {categories.isPending ? (
        <Loading />
      ) : categories.isError ? (
        <Alert>{errorMessage(categories.error)}</Alert>
      ) : (
        <div className="space-y-10">
          {(["expense", "income"] as const).map((type) => (
            <section key={type} aria-labelledby={`${type}-title`}>
              <div className="mb-3 flex items-center justify-between">
                <h2 id={`${type}-title`} className="text-lg font-semibold text-zinc-900">
                  {type === "expense" ? "Gastos" : "Receitas"}
                </h2>
                <Button variant="secondary" onClick={() => setEditing({ mode: "new", type, parent: null })}>
                  Nova categoria
                </Button>
              </div>
              <ul className="grid gap-3 md:grid-cols-2">
                {categoryTree(categories.data.filter((c) => c.type === type)).map(({ parent, children }) => (
                  <li key={parent.id}>
                    <Card className={parent.is_archived ? "h-full opacity-60" : "h-full"}>
                      <div className="flex items-center justify-between gap-2">
                        <button
                          type="button"
                          className="font-medium text-zinc-900 hover:underline"
                          onClick={() => setEditing({ mode: "edit", category: parent })}
                        >
                          {parent.name}
                        </button>
                        {parent.is_archived && <Badge>arquivada</Badge>}
                      </div>
                      <ul className="mt-3 flex flex-wrap gap-2">
                        {children.map((child) => (
                          <li key={child.id}>
                            <button
                              type="button"
                              onClick={() => setEditing({ mode: "edit", category: child })}
                              className={`rounded-full border px-3 py-1 text-xs hover:border-emerald-600 ${
                                child.is_archived
                                  ? "border-dashed text-zinc-400"
                                  : "border-zinc-300 text-zinc-700"
                              }`}
                            >
                              {child.name}
                            </button>
                          </li>
                        ))}
                        <li>
                          <button
                            type="button"
                            onClick={() => setEditing({ mode: "new", type, parent })}
                            className="rounded-full px-3 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
                          >
                            + subcategoria
                          </button>
                        </li>
                      </ul>
                    </Card>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
      <Dialog
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={
          editing?.mode === "edit"
            ? "Editar categoria"
            : editing?.parent
              ? `Nova subcategoria de ${editing.parent.name}`
              : "Nova categoria"
        }
      >
        {editing && <CategoryForm editing={editing} onDone={() => setEditing(null)} />}
      </Dialog>
    </>
  );
}

function CategoryForm({ editing, onDone }: { editing: Editing; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: CATEGORIES });
    onDone();
  };
  const category = editing.mode === "edit" ? editing.category : null;

  const save = useMutation({
    mutationFn: (values: Record<string, string>) =>
      editing.mode === "edit"
        ? api.patch(`/categories/${editing.category.id}`, { name: values.name })
        : api.post("/categories", {
            name: values.name,
            type: editing.type,
            parent_id: editing.parent?.id ?? null,
          }),
    onSuccess: done,
  });
  const archive = useMutation({
    mutationFn: () => api.patch(`/categories/${category!.id}`, { is_archived: !category!.is_archived }),
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: () => api.delete(`/categories/${category!.id}`),
    onSuccess: done,
  });
  const error = save.error ?? archive.error ?? remove.error;

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate(formValues(event.currentTarget));
      }}
    >
      <Field label="Nome" error={fieldError(save.error, "name")}>
        {(props) => <Input {...props} name="name" defaultValue={category?.name} required maxLength={60} />}
      </Field>
      <Alert>{error && !fieldError(error, "name") ? errorMessage(error) : null}</Alert>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {category ? (
          confirmDelete ? (
            <span className="flex items-center gap-2 text-sm">
              Excluir mesmo?
              <Button
                variant="danger"
                className="px-3 py-1"
                busy={remove.isPending}
                onClick={() => remove.mutate()}
              >
                Sim, excluir
              </Button>
            </span>
          ) : (
            <span className="flex gap-1">
              <Button
                variant="ghost"
                className="px-2"
                busy={archive.isPending}
                onClick={() => archive.mutate()}
              >
                {category.is_archived ? "Desarquivar" : "Arquivar"}
              </Button>
              <Button variant="ghost" className="px-2 text-red-700" onClick={() => setConfirmDelete(true)}>
                Excluir
              </Button>
            </span>
          )
        ) : (
          <span />
        )}
        <Button type="submit" busy={save.isPending}>
          Salvar
        </Button>
      </div>
    </form>
  );
}
