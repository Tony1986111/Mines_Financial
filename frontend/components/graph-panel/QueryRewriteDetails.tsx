interface QueryRewriteDetailsProps {
  state: Record<string, unknown>;
}

export default function QueryRewriteDetails({ state }: QueryRewriteDetailsProps) {
  const companyQueries = (state.company_queries as Array<{ company: string; query: string }> | undefined) ?? [];

  if (companyQueries.length === 0) {
    return <p className="text-[10px] italic text-[#7a9ab8] dark:text-[#3d5878] mt-2">pending for company queries</p>;
  }

  return (
    <div className="mt-2 space-y-1 text-xs font-mono bg-[#eef4fb] dark:bg-[#060c14] border border-[#cddcea] dark:border-[#162840] rounded-lg p-3">
      {companyQueries.map(({ company, query }) => (
        <div key={company} className="flex gap-2 items-start">
          <span className="text-[#1a4a8a] dark:text-[#7aade8] font-semibold shrink-0 w-10">{company}:</span>
          <span className="text-[#0a1e38] dark:text-[#c4d8f0] break-all leading-relaxed">{query}</span>
        </div>
      ))}
    </div>
  );
}
