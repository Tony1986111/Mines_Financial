"use client";

import { useEffect, useState } from "react";
import { deleteConclusion, fetchConclusions, updateConclusion, type Conclusion } from "@/lib/api";

interface MemoryModalProps {
  open: boolean;
  onClose: () => void;
}

function CompanyTag({ label }: { label: string }) {
  return (
    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide bg-[#1a4a8a]/15 text-[#7eb3e8] border border-[#1a4a8a]/20">
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
    <div className="rounded-xl border border-[#1e3858] bg-[#091524] overflow-hidden">
      {/* Header row */}
      <div
        className="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-[#0d1c2e] transition-colors"
        onClick={() => { setExpanded(e => !e); setEditing(false); setConfirmDelete(false); }}
      >
        <span className="mt-0.5 text-[10px] text-[#3d5878] shrink-0">{expanded ? "▼" : "▶"}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#c4d8f0] leading-snug">{item.query}</p>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {companies.map(c => <CompanyTag key={c} label={c} />)}
            {item.fy && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide bg-amber-500/10 text-amber-400 border border-amber-500/20">
                {item.fy}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 ml-2" onClick={e => e.stopPropagation()}>
          <button
            onClick={() => { setExpanded(true); setEditing(e => !e); setConfirmDelete(false); }}
            className="text-[10px] px-2 py-1 rounded-md border border-[#1e3858] text-[#7a9ab8] hover:text-[#c4d8f0] hover:border-[#5a8fc8] hover:bg-[#0d1c2e] transition-colors"
          >
            Edit
          </button>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="text-[10px] px-2 py-1 rounded-md border border-rose-500/20 text-rose-400/60 hover:text-rose-400 hover:border-rose-500/50 hover:bg-rose-500/10 transition-colors"
            >
              Delete
            </button>
          ) : (
            <div className="flex items-center gap-1">
              <button
                onClick={handleDelete}
                className="text-[10px] px-2 py-1 rounded-md bg-rose-500/20 border border-rose-500/40 text-rose-400 hover:bg-rose-500/30 transition-colors"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="text-[10px] px-2 py-1 rounded-md border border-[#1e3858] text-[#7a9ab8] hover:text-[#c4d8f0] transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Expanded answer */}
      {expanded && (
        <div className="border-t border-[#1e3858] px-4 py-3 bg-[#060c14]">
          {editing ? (
            <div className="flex flex-col gap-2">
              <textarea
                value={draft}
                onChange={e => setDraft(e.target.value)}
                rows={8}
                className="w-full bg-[#091524] border border-[#1e3858] rounded-lg px-3 py-2 text-xs text-[#a8c4e0] font-mono leading-relaxed resize-y focus:outline-none focus:border-[#5a8fc8]"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => { setDraft(item.answer); setEditing(false); }}
                  className="text-[10px] px-3 py-1.5 rounded-md border border-[#1e3858] text-[#7a9ab8] hover:text-[#c4d8f0] transition-colors"
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
            <pre className="text-xs text-[#a8c4e0] whitespace-pre-wrap leading-relaxed font-mono">
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
      className="fixed inset-0 z-50 flex items-start justify-center bg-[#030810]/80 px-4 py-6 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        className="flex h-[min(820px,calc(100vh-48px))] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-[#1e3858] bg-[#091524] shadow-2xl shadow-black/40"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-[#162840] px-5 bg-[#091524]">
          <div className="min-w-0">
            <h2 className="text-sm font-bold tracking-tight text-[#dce8f8]">Semantic Memory</h2>
            <p className="text-[10px] text-[#3d5878] font-mono">
              {items.length} cached conclusion{items.length !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search…"
              className="h-7 w-44 rounded-lg border border-[#1e3858] bg-[#060c14] px-2.5 text-xs text-[#a8c4e0] placeholder-[#3d5878] focus:outline-none focus:border-[#5a8fc8]"
            />
            <button
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-lg text-sm text-[#3d5878] hover:bg-[#0d1c2e] hover:text-[#c4d8f0] transition-colors"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <p className="text-center text-sm text-[#3d5878] italic mt-10">Loading…</p>
          )}
          {!loading && filtered.length === 0 && (
            <p className="text-center text-sm text-[#3d5878] italic mt-10">
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
