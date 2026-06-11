import ProgressCard, { type ProgressCardData } from "@/components/ProgressCard";

interface ProgressMessageProps {
  cards: ProgressCardData[];
}

export default function ProgressMessage({ cards }: ProgressMessageProps) {
  if (cards.length === 0) return null;

  return (
    <div className="flex gap-2.5 mb-3 md:gap-3">
      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#1e5cba] to-[#1a4a8a] shrink-0 flex items-center justify-center text-[10px] font-bold text-white mt-0.5 ring-1 ring-white/10">
        AI
      </div>
      <div className="min-w-0 flex-1 flex flex-col gap-2">
        {cards.map(card => (
          <ProgressCard key={card.id} card={card} />
        ))}
      </div>
    </div>
  );
}
