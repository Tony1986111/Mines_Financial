interface MemoryModalHeaderProps {
  itemCount: number;
  search: string;
  onSearchChange: (value: string) => void;
  onClose: () => void;
}

export default function MemoryModalHeader({
  itemCount,
  search,
  onSearchChange,
  onClose,
}: MemoryModalHeaderProps) {
  return (
    <div className="flex min-h-14 shrink-0 flex-wrap items-center gap-3 border-b border-[#cddcea] px-3 py-3 bg-white md:h-14 md:flex-nowrap md:px-5 md:py-0 dark:border-[#162840] dark:bg-[#091524]">
      <div className="min-w-0">
        <h2 className="text-sm font-bold tracking-tight text-[#0a1e38] dark:text-[#dce8f8]">Semantic Memory</h2>
        <p className="text-[10px] text-[#7a9ab8] font-mono dark:text-[#3d5878]">
          {itemCount} cached conclusion{itemCount !== 1 ? "s" : ""}
        </p>
      </div>
      <div className="flex w-full items-center gap-2 md:ml-auto md:w-auto">
        <input
          type="text"
          value={search}
          onChange={event => onSearchChange(event.target.value)}
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
  );
}
