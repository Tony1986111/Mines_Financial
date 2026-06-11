import ConclusionRow from "@/components/memory-modal/ConclusionRow";
import type { Conclusion } from "@/lib/api";

interface MemoryListProps {
  loading: boolean;
  search: string;
  items: Conclusion[];
  onUpdated: (id: string, answer: string) => void;
  onDeleted: (id: string) => void;
}

export default function MemoryList({
  loading,
  search,
  items,
  onUpdated,
  onDeleted,
}: MemoryListProps) {
  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-2 md:p-4">
      {loading && (
        <p className="text-center text-sm text-[#7a9ab8] italic mt-10 dark:text-[#3d5878]">Loading…</p>
      )}
      {!loading && items.length === 0 && (
        <p className="text-center text-sm text-[#7a9ab8] italic mt-10 dark:text-[#3d5878]">
          {search ? "No matches found." : "No semantic memory entries yet."}
        </p>
      )}
      {!loading && items.map(item => (
        <ConclusionRow
          key={item.id}
          item={item}
          onUpdated={onUpdated}
          onDeleted={onDeleted}
        />
      ))}
    </div>
  );
}
