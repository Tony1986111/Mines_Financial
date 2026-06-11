interface MessageAvatarProps {
  role: "user" | "assistant";
}

export default function MessageAvatar({ role }: MessageAvatarProps) {
  const isUser = role === "user";

  return (
    <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold mt-0.5 ring-1 ring-white/10 ${
      isUser
        ? "bg-[#1a4a8a] text-white"
        : "bg-gradient-to-br from-[#1e5cba] to-[#1a4a8a] text-white"
    }`}>
      {isUser ? "U" : "AI"}
    </div>
  );
}
