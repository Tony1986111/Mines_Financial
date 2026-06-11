"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchConclusions, type Conclusion } from "@/lib/api";

export function useMemoryConclusions(open: boolean) {
  const [items, setItems] = useState<Conclusion[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetchConclusions()
      .then(setItems)
      .finally(() => setLoading(false));
  }, [open]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;

    return items.filter(item =>
      item.query.toLowerCase().includes(q) ||
      item.answer.toLowerCase().includes(q) ||
      item.companies.toLowerCase().includes(q)
    );
  }, [items, search]);

  function updateLocalConclusion(id: string, answer: string) {
    setItems(prev => prev.map(item => item.id === id ? { ...item, answer } : item));
  }

  function removeLocalConclusion(id: string) {
    setItems(prev => prev.filter(item => item.id !== id));
  }

  return {
    items,
    filtered,
    loading,
    search,
    setSearch,
    updateLocalConclusion,
    removeLocalConclusion,
  };
}
