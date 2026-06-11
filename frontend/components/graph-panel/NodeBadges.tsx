import type { NodeBadge } from "@/lib/graphNodeMeta";

interface NodeBadgesProps {
  badges: NodeBadge[];
}

export default function NodeBadges({ badges }: NodeBadgesProps) {
  return (
    <>
      {badges.map((badge) => (
        <span
          key={`${badge.label}-${badge.className}`}
          className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${badge.className}`}
        >
          {badge.label}
        </span>
      ))}
    </>
  );
}
