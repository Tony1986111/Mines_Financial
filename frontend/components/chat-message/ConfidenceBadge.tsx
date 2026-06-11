interface ConfidenceBadgeProps {
  confidence?: string;
  unsupportedClaims?: Array<{ claim: string; basis: string }>;
}

const basisLabel: Record<string, string> = {
  calculation: "calculated from report data",
  interpolation: "estimated from report data",
  general_knowledge: "not found in reports",
};

export default function ConfidenceBadge({
  confidence,
  unsupportedClaims,
}: ConfidenceBadgeProps) {
  if (!confidence) return null;

  return (
    <div className={`text-[11px] font-semibold mb-2.5 pb-2 border-b ${
      confidence === "high"
        ? "text-emerald-600 dark:text-emerald-400 border-emerald-500/15"
        : confidence === "medium"
        ? "text-amber-600 dark:text-amber-400 border-amber-500/15"
        : "text-rose-600 dark:text-rose-400 border-rose-500/15"
    }`}>
      <div className="flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
          confidence === "high" ? "bg-emerald-500 dark:bg-emerald-400"
          : confidence === "medium" ? "bg-amber-500 dark:bg-amber-400"
          : "bg-rose-500 dark:bg-rose-400"
        }`} />
        {confidence === "high"
          ? "High Confidence — All facts verified against retrieved documents"
          : confidence === "medium"
          ? "Medium Confidence — Some claims could not be fully verified"
          : "Low Confidence — Please cross-check with original annual reports"}
      </div>
      {confidence !== "high" && unsupportedClaims && unsupportedClaims.length > 0 && (
        <div className="mt-1.5 ml-3 font-normal opacity-80 flex flex-col gap-0.5">
          <span className="font-semibold">Unverified:</span>
          {unsupportedClaims.map((claim, i) => (
            <div key={i} className="flex gap-1.5">
              <span className="shrink-0 font-semibold">{i + 1}.</span>
              <span>
                {claim.claim}{" "}
                <span className="opacity-60 text-[10px]">({basisLabel[claim.basis] ?? claim.basis})</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
