interface CompanyTagProps {
  label: string;
}

export default function CompanyTag({ label }: CompanyTagProps) {
  return (
    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide bg-[#1a4a8a]/15 text-[#1a4a8a] border border-[#1a4a8a]/20 dark:text-[#7eb3e8]">
      {label}
    </span>
  );
}
