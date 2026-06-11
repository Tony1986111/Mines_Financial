interface ConclusionEditorProps {
  value: string;
  saving: boolean;
  onChange: (value: string) => void;
  onCancel: () => void;
  onSave: () => void;
}

export default function ConclusionEditor({
  value,
  saving,
  onChange,
  onCancel,
  onSave,
}: ConclusionEditorProps) {
  return (
    <div className="flex flex-col gap-2">
      <textarea
        value={value}
        onChange={event => onChange(event.target.value)}
        rows={8}
        className="w-full bg-white border border-[#cddcea] rounded-lg px-3 py-2 text-xs text-[#1a3a5c] font-mono leading-relaxed resize-y focus:outline-none focus:border-[#1a4a8a] dark:bg-[#091524] dark:border-[#1e3858] dark:text-[#a8c4e0] dark:focus:border-[#5a8fc8]"
      />
      <div className="flex flex-wrap gap-2 justify-end">
        <button
          onClick={onCancel}
          className="text-[10px] px-3 py-1.5 rounded-md border border-[#cddcea] text-[#5a7a9a] hover:text-[#0a1e38] transition-colors dark:border-[#1e3858] dark:text-[#7a9ab8] dark:hover:text-[#c4d8f0]"
        >
          Cancel
        </button>
        <button
          onClick={onSave}
          disabled={saving}
          className="text-[10px] px-3 py-1.5 rounded-md bg-[#1a4a8a] text-white hover:bg-[#1e5cba] disabled:opacity-50 transition-colors"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
