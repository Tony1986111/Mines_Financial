"use client";

import { useEffect, useState } from "react";
import { deleteConclusion, fetchConclusions, updateConclusion, type Conclusion } from "@/lib/api";

interface MemoryModalProps {
  open: boolean;
  onClose: () => void;
}

function CompanyTag({ label }: { label: string }) {
  return (
    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide bg-[#1a4a8a]/15 text-[#1a4a8a] border border-[#1a4a8a]/20 dark:text-[#7eb3e8]">
      {label}
    </span>
  );
}

function ConclusionRow({
  item,
  onUpdated,
  onDeleted,
}: {
  item: Conclusion;
  onUpdated: (id: string, answer: string) => void;
  onDeleted: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.answer);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const companies = item.companies ? item.companies.split(",").map(s => s.trim()).filter(Boolean) : [];

  async function handleSave() {
    setSaving(true);
    await updateConclusion(item.id, draft);
    onUpdated(item.id, draft);
    setSaving(false);
    setEditing(false);
  }

  async function handleDelete() {
    await deleteConclusion(item.id);
    onDeleted(item.id);
  }

  return (
    <div className="rounded-xl border border-[#cddcea] bg-white overflow-hidden dark:border-[#1e3858] dark:bg-[#091524]">
      {/* Header row */}
      <div
        className="flex flex-col gap-3 px-3 py-3 cursor-pointer hover:bg-[#f0f6ff] transition-colors md:flex-row md:items-start md:px-4 dark:hover:bg-[#0d1c2e]"
        onClick={() => { setExpanded(e => !e); setEditing(false); setConfirmDelete(false); }}
      >
        <span className="mt-0.5 text-[10px] text-[#7a9ab8] shrink-0 dark:text-[#3d5878]">{expanded ? "▼" : "▶"}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#0a1e38] leading-snug break-words dark:text-[#c4d8f0]">{item.query}</p>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {companies.map(c => <CompanyTag key={c} label={c} />)}
            {item.fy && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide bg-amber-500/10 text-amber-600 border border-amber-500/20 dark:text-amber-400">
                {item.fy}
              </span>
            )}
          </div>
        </div>
        <div className="ml-5 flex flex-wrap items-center justify-end gap-1.5 shrink-0 md:ml-2" onClick={e => e.stopPropagation()}>
          <button
            onClick={() => { setExpanded(true); setEditing(e => !e); setConfirmDelete(false); }}
            className="text-[10px] px-2 py-1 rounded-md border border-[#cddcea] text-[#5a7a9a] hover:text-[#0a1e38] hover:border-[#1a4a8a] hover:bg-[#e8f0fa] transition-colors dark:border-[#1e3858] dark:text-[#7a9ab8] dark:hover:text-[#c4d8f0] dark:hover:border-[#5a8fc8] dark:hover:bg-[#0d1c2e]"
          >
            Edit
          </button>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="text-[10px] px-2 py-1 rounded-md border border-rose-300 text-rose-400/80 hover:text-rose-600 hover:border-rose-400 hover:bg-rose-50 transition-colors dark:border-rose-500/20 dark:text-rose-400/60 dark:hover:text-rose-400 dark:hover:border-rose-500/50 dark:hover:bg-rose-500/10"
            >
              Delete
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <button
                onClick={handleDelete}
                className="text-[10px] px-2 py-1 rounded-md bg-rose-500/20 border border-rose-500/40 text-rose-600 hover:bg-rose-500/30 transition-colors dark:text-rose-400"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="text-[10px] px-2 py-1 rounded-md border border-[#cddcea] text-[#5a7a9a] hover:text-[#0a1e38] transition-colors dark:border-[#1e3858] dark:text-[#7a9ab8] dark:hover:text-[#c4d8f0]"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Expanded answer */}
      {expanded && (
        <div className="border-t border-[#cddcea] px-3 py-3 bg-[#f5f8fd] md:px-4 dark:border-[#1e3858] dark:bg-[#060c14]">
          {editing ? (
            <div className="flex flex-col gap-2">
              <textarea
                value={draft}
                onChange={e => setDraft(e.target.value)}
                rows={8}
                className="w-full bg-white border border-[#cddcea] rounded-lg px-3 py-2 text-xs text-[#1a3a5c] font-mono leading-relaxed resize-y focus:outline-none focus:border-[#1a4a8a] dark:bg-[#091524] dark:border-[#1e3858] dark:text-[#a8c4e0] dark:focus:border-[#5a8fc8]"
              />
              <div className="flex flex-wrap gap-2 justify-end">
                <button
                  onClick={() => { setDraft(item.answer); setEditing(false); }}
                  className="text-[10px] px-3 py-1.5 rounded-md border border-[#cddcea] text-[#5a7a9a] hover:text-[#0a1e38] transition-colors dark:border-[#1e3858] dark:text-[#7a9ab8] dark:hover:text-[#c4d8f0]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="text-[10px] px-3 py-1.5 rounded-md bg-[#1a4a8a] text-white hover:bg-[#1e5cba] disabled:opacity-50 transition-colors"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            </div>
          ) : (
            <pre className="text-xs text-[#1a3a5c] whitespace-pre-wrap break-words leading-relaxed font-mono dark:text-[#a8c4e0]">
              {item.answer}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

export default function MemoryModal({ open, onClose }: MemoryModalProps) {
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

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const filtered = search.trim()
    ? items.filter(i =>
        i.query.toLowerCase().includes(search.toLowerCase()) ||
        i.answer.toLowerCase().includes(search.toLowerCase()) ||
        i.companies.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-2 py-3 backdrop-blur-md md:px-4 md:py-6 dark:bg-[#030810]/80"
      onClick={onClose}
    >
      <div
        className="flex h-[calc(100dvh-1.5rem)] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-[#cddcea] bg-white shadow-2xl shadow-black/20 md:h-[min(820px,calc(100vh-48px))] dark:border-[#1e3858] dark:bg-[#091524] dark:shadow-black/40"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex min-h-14 shrink-0 flex-wrap items-center gap-3 border-b border-[#cddcea] px-3 py-3 bg-white md:h-14 md:flex-nowrap md:px-5 md:py-0 dark:border-[#162840] dark:bg-[#091524]">
          <div className="min-w-0">
            <h2 className="text-sm font-bold tracking-tight text-[#0a1e38] dark:text-[#dce8f8]">Semantic Memory</h2>
            <p className="text-[10px] text-[#7a9ab8] font-mono dark:text-[#3d5878]">
              {items.length} cached conclusion{items.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="flex w-full items-center gap-2 md:ml-auto md:w-auto">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search…"
              className="h-8 min-w-0 flex-1 rounded-lg border border-[#cddcea] bg-[#f5f8fd] px-2.5 text-xs text-[#0a1e38] placeholder-[#94b0cc] focus:outline-none focus:border-[#1a4a8a] md:h-7 md:w-44 md:flex-none dark:border-[#1e3858] dark:bg-[#060c14] dark:text-[#a8c4e0] dark:placeholder-[#3d5878] dark:focus:border-[#5a8fc8]"
            />
            <button
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-sm text-[#94b0cc] hover:bg-[#e8f0fa] hover:text-[#0a1e38] transition-colors dark:text-[#3d5878] dark:hover:bg-[#0d1c2e] dark:hover:text-[#c4d8f0]"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 md:p-4">
          {loading && (
            <p className="text-center text-sm text-[#7a9ab8] italic mt-10 dark:text-[#3d5878]">Loading…</p>
          )}
          {!loading && filtered.length === 0 && (
            <p className="text-center text-sm text-[#7a9ab8] italic mt-10 dark:text-[#3d5878]">
              {search ? "No matches found." : "No semantic memory entries yet."}
            </p>
          )}
          {!loading && filtered.map(item => (
            <ConclusionRow
              key={item.id}
              item={item}
              onUpdated={(id, answer) =>
                setItems(prev => prev.map(i => i.id === id ? { ...i, answer } : i))
              }
              onDeleted={id => setItems(prev => prev.filter(i => i.id !== id))}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
