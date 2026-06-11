"use client";

import { useState } from "react";
import CompanyTag from "@/components/memory-modal/CompanyTag";
import ConclusionEditor from "@/components/memory-modal/ConclusionEditor";
import { deleteConclusion, updateConclusion, type Conclusion } from "@/lib/api";

interface ConclusionRowProps {
  item: Conclusion;
  onUpdated: (id: string, answer: string) => void;
  onDeleted: (id: string) => void;
}

export default function ConclusionRow({
  item,
  onUpdated,
  onDeleted,
}: ConclusionRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.answer);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const companies = item.companies ? item.companies.split(",").map(value => value.trim()).filter(Boolean) : [];

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
      <div
        className="flex flex-col gap-3 px-3 py-3 cursor-pointer hover:bg-[#f0f6ff] transition-colors md:flex-row md:items-start md:px-4 dark:hover:bg-[#0d1c2e]"
        onClick={() => { setExpanded(current => !current); setEditing(false); setConfirmDelete(false); }}
      >
        <span className="mt-0.5 text-[10px] text-[#7a9ab8] shrink-0 dark:text-[#3d5878]">{expanded ? "▼" : "▶"}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#0a1e38] leading-snug break-words dark:text-[#c4d8f0]">{item.query}</p>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {companies.map(company => <CompanyTag key={company} label={company} />)}
            {item.fy && (
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide bg-amber-500/10 text-amber-600 border border-amber-500/20 dark:text-amber-400">
                {item.fy}
              </span>
            )}
          </div>
        </div>
        <div className="ml-5 flex flex-wrap items-center justify-end gap-1.5 shrink-0 md:ml-2" onClick={event => event.stopPropagation()}>
          <button
            onClick={() => { setExpanded(true); setEditing(current => !current); setConfirmDelete(false); }}
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

      {expanded && (
        <div className="border-t border-[#cddcea] px-3 py-3 bg-[#f5f8fd] md:px-4 dark:border-[#1e3858] dark:bg-[#060c14]">
          {editing ? (
            <ConclusionEditor
              value={draft}
              saving={saving}
              onChange={setDraft}
              onCancel={() => { setDraft(item.answer); setEditing(false); }}
              onSave={handleSave}
            />
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
