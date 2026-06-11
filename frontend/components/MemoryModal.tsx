"use client";

import { useEffect } from "react";
import MemoryList from "@/components/memory-modal/MemoryList";
import MemoryModalHeader from "@/components/memory-modal/MemoryModalHeader";
import { useMemoryConclusions } from "@/hooks/useMemoryConclusions";

interface MemoryModalProps {
  open: boolean;
  onClose: () => void;
}

export default function MemoryModal({ open, onClose }: MemoryModalProps) {
  const {
    items,
    filtered,
    loading,
    search,
    setSearch,
    updateLocalConclusion,
    removeLocalConclusion,
  } = useMemoryConclusions(open);

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-2 py-3 backdrop-blur-md md:px-4 md:py-6 dark:bg-[#030810]/80"
      onClick={onClose}
    >
      <div
        className="flex h-[calc(100dvh-1.5rem)] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-[#cddcea] bg-white shadow-2xl shadow-black/20 md:h-[min(820px,calc(100vh-48px))] dark:border-[#1e3858] dark:bg-[#091524] dark:shadow-black/40"
        onClick={event => event.stopPropagation()}
      >
        <MemoryModalHeader
          itemCount={items.length}
          search={search}
          onSearchChange={setSearch}
          onClose={onClose}
        />
        <MemoryList
          loading={loading}
          search={search}
          items={filtered}
          onUpdated={updateLocalConclusion}
          onDeleted={removeLocalConclusion}
        />
      </div>
    </div>
  );
}
