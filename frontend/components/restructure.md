# `MemoryModal.tsx` Restructure Plan

## Is It Necessary?

Worth splitting, but not urgent.

`MemoryModal.tsx` is 227 lines. It is still manageable, but it mixes API lifecycle, search filtering, modal layout, row expansion, edit state, save/delete calls, and small presentational tags in one file. In production, this should be split once the feature is stable or before adding more memory actions.

## Target Structure

```txt
frontend/
  components/
    MemoryModal.tsx
    memory-modal/
      MemoryModalHeader.tsx
      MemoryList.tsx
      ConclusionRow.tsx
      ConclusionEditor.tsx
      CompanyTag.tsx

  hooks/
    useMemoryConclusions.ts
```

## Phase 1: Extract UI Pieces

Move these first, preserving class names:

- `CompanyTag` -> `memory-modal/CompanyTag.tsx`
- modal header/search/close UI -> `memory-modal/MemoryModalHeader.tsx`
- loading/empty/list rendering -> `memory-modal/MemoryList.tsx`
- answer edit textarea/buttons -> `memory-modal/ConclusionEditor.tsx`
- row expansion/edit/delete UI -> `memory-modal/ConclusionRow.tsx`

Keep `MemoryModal.tsx` as the shell that composes these pieces.

## Phase 2: Extract Data Hook

Create:

```txt
frontend/hooks/useMemoryConclusions.ts
```

Move:

- `fetchConclusions` lifecycle when modal opens
- `items`
- `loading`
- `search`
- filtered results
- update/delete local state callbacks

Return:

```ts
{
  items,
  filtered,
  loading,
  search,
  setSearch,
  updateLocalConclusion,
  removeLocalConclusion,
}
```

Keep actual `updateConclusion` and `deleteConclusion` calls inside `ConclusionRow` for now, or move them into the hook later if you want stricter separation.

## Final Shape

`MemoryModal.tsx` should end around 60-90 lines:

```tsx
export default function MemoryModal({ open, onClose }: MemoryModalProps) {
  const memory = useMemoryConclusions(open);
  useEscapeToClose(open, onClose);

  if (!open) return null;

  return (
    <ModalShell onClose={onClose}>
      <MemoryModalHeader ... />
      <MemoryList ... />
    </ModalShell>
  );
}
```

## Checks

Run after each phase:

```bash
npx tsc --noEmit
```

Manual checks:

- open/close modal
- Escape closes modal
- search filters query/answer/company
- expand row
- edit/save answer
- cancel edit
- delete confirmation
- delete cancel
- empty state
