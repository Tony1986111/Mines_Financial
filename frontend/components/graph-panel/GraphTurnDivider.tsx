interface GraphTurnDividerProps {
  query?: unknown;
}

export default function GraphTurnDivider({ query }: GraphTurnDividerProps) {
  const label = String(query ?? "");

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 my-1">
      <div className="flex-1 h-px bg-[#cddcea] dark:bg-[#162840]" />
      <span
        className="text-[9px] text-[#94b0cc] dark:text-[#3d5878] font-mono truncate max-w-[130px]"
        title={label}
      >
        {label}
      </span>
      <div className="flex-1 h-px bg-[#cddcea] dark:bg-[#162840]" />
    </div>
  );
}
