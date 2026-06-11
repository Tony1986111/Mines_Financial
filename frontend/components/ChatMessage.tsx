"use client";

import { useEffect, useState } from "react";
import ConfidenceBadge from "@/components/chat-message/ConfidenceBadge";
import MessageAvatar from "@/components/chat-message/MessageAvatar";
import ProgressMessage from "@/components/chat-message/ProgressMessage";
import SourceModal from "@/components/chat-message/SourceModal";
import SourcesBar from "@/components/chat-message/SourcesBar";
import SystemMessage from "@/components/chat-message/SystemMessage";
import { renderContent } from "@/components/chat-message/renderContent";
import { stripSourcesSection } from "@/lib/chatContent";
import type { Message } from "@/types/chat";

export type { Message, SourceItem } from "@/types/chat";

interface ChatMessageProps {
  message: Message;
  typewriter?: boolean;
}

export default function ChatMessage({
  message,
  typewriter = false,
}: ChatMessageProps) {
  const [displayed, setDisplayed] = useState(typewriter ? "" : message.content);
  const [cursorVisible, setCursorVisible] = useState(typewriter);
  const [activeSourceIdx, setActiveSourceIdx] = useState<number | null>(null);

  useEffect(() => {
    if (!typewriter) {
      setDisplayed(message.content);
      setCursorVisible(false);
      return;
    }

    setDisplayed("");
    setCursorVisible(true);
    let i = 0;
    const text = message.content;
    const id = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(id);
        setCursorVisible(false);
      }
    }, 12);

    return () => clearInterval(id);
  }, [message.content, typewriter]);

  if (message.role === "progress") {
    return <ProgressMessage cards={message.cards ?? []} />;
  }

  if (message.role === "system") {
    return <SystemMessage content={message.content} />;
  }

  const isUser = message.role === "user";
  const sources = message.sources ?? [];
  const cleanText = stripSourcesSection(displayed);

  return (
    <>
      <div className={`flex gap-2.5 mb-4 md:gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
        <MessageAvatar role={isUser ? "user" : "assistant"} />

        <div className={`min-w-0 max-w-[calc(100%-2.375rem)] rounded-2xl px-3.5 py-3 text-sm leading-relaxed [overflow-wrap:anywhere] md:max-w-[75%] md:px-4 ${
          isUser
            ? "bg-gradient-to-b from-[#1e5cba] to-[#1a4a8a] text-white rounded-tr-sm shadow-sm shadow-[#1a4a8a]/20"
            : "bg-white dark:bg-[#0d1c2e] text-[#0a1e38] dark:text-[#c4d8f0] border border-[#cddcea] dark:border-[#162840] rounded-tl-sm shadow-sm dark:shadow-none"
        }`}>
          {!isUser && (
            <ConfidenceBadge
              confidence={message.confidence}
              unsupportedClaims={message.unsupportedClaims}
            />
          )}

          {renderContent({
            text: cleanText,
            chartData: message.chartData,
            sources,
          })}
          {cursorVisible && (
            <span className="inline-block w-0.5 h-3.5 bg-[#7eb3e8] ml-0.5 align-middle animate-blink" />
          )}

          {!isUser && (
            <SourcesBar
              sources={sources}
              onSelectSource={setActiveSourceIdx}
            />
          )}
        </div>
      </div>

      {activeSourceIdx !== null && sources[activeSourceIdx] && (
        <SourceModal
          source={sources[activeSourceIdx]}
          index={activeSourceIdx + 1}
          onClose={() => setActiveSourceIdx(null)}
        />
      )}
    </>
  );
}
