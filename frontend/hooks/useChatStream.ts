"use client";

import { useCallback, type Dispatch, type FormEvent, type RefObject, type SetStateAction } from "react";
import type { ProgressCardData } from "@/components/ProgressCard";
import { saveProgress, streamMessage, type ChartSpec, type SourceRef } from "@/lib/api";
import { nodeEventToCard, toCards } from "@/lib/progressEvents";
import { loadThreads, saveThread, type StoredThread } from "@/lib/threadStorage";
import type { StreamBuffer } from "@/hooks/useThreads";
import type { Message } from "@/types/chat";
import type { GraphNodeEvent } from "@/types/graph";

interface UseChatStreamOptions {
  threadId: string | null;
  threadIdRef: RefObject<string | null>;
  streamBufferRef: RefObject<StreamBuffer | null>;
  inputRef: RefObject<HTMLInputElement | null>;
  input: string;
  messages: Message[];
  graphEvents: GraphNodeEvent[];
  loading: boolean;
  awaitingClarification: boolean;
  setInput: Dispatch<SetStateAction<string>>;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setGraphEvents: Dispatch<SetStateAction<GraphNodeEvent[]>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setStreamingThreadId: Dispatch<SetStateAction<string | null>>;
  setStreamingLabel: Dispatch<SetStateAction<string>>;
  setTypewriterIdx: Dispatch<SetStateAction<number | null>>;
  setAwaitingClarification: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setThreads: Dispatch<SetStateAction<StoredThread[]>>;
}

export function useChatStream({
  threadId,
  threadIdRef,
  streamBufferRef,
  inputRef,
  input,
  messages,
  graphEvents,
  loading,
  awaitingClarification,
  setInput,
  setMessages,
  setGraphEvents,
  setLoading,
  setStreamingThreadId,
  setStreamingLabel,
  setTypewriterIdx,
  setAwaitingClarification,
  setError,
  setThreads,
}: UseChatStreamOptions) {
  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !threadId || loading) return;

    const userMessage = input.trim();
    const submittedThreadId = threadId;
    setInput("");
    setError(null);
    const next: Message[] = [...messages, { role: "user", content: userMessage }];
    setMessages(next);
    setLoading(true);
    setStreamingThreadId(submittedThreadId);
    setStreamingLabel(userMessage.slice(0, 60));
    setTypewriterIdx(null);

    const turnDivider: GraphNodeEvent = { node: "__turn__", status: "done", state: { query: userMessage.slice(0, 60) } };
    const baseEvents: GraphNodeEvent[] = graphEvents.length > 0 ? [...graphEvents, turnDivider] : [];
    setGraphEvents(baseEvents);

    streamBufferRef.current = { threadId: submittedThreadId, messages: next, graphEvents: baseEvents };

    function bufMessages(updater: (prev: Message[]) => Message[]) {
      if (streamBufferRef.current?.threadId === submittedThreadId) {
        streamBufferRef.current.messages = updater(streamBufferRef.current.messages);
      }
      if (threadIdRef.current === submittedThreadId) {
        setMessages(updater);
      }
    }

    function bufGraphEvents(updater: (prev: GraphNodeEvent[]) => GraphNodeEvent[]) {
      if (streamBufferRef.current?.threadId === submittedThreadId) {
        streamBufferRef.current.graphEvents = updater(streamBufferRef.current.graphEvents);
      }
      if (threadIdRef.current === submittedThreadId) {
        setGraphEvents(updater);
      }
    }

    let currentCards: ProgressCardData[] = [];
    const pendingSubgraphDones: Array<{ node: string; state?: Record<string, unknown> }> = [];
    let progressAdded = false;
    const progressIdx = next.length;

    function flushProgressMessage() {
      if (!progressAdded && currentCards.length > 0) {
        progressAdded = true;
        bufMessages(prev => [
          ...prev,
          { role: "progress", content: "", cards: [...currentCards] },
        ]);
      } else if (progressAdded) {
        bufMessages(prev => {
          const arr = [...prev];
          if (arr[progressIdx]?.role === "progress") {
            arr[progressIdx] = { role: "progress", content: "", cards: [...currentCards] };
          }
          return arr;
        });
      }
    }

    try {
      let finalAnswer = "";
      let finalChartData: ChartSpec[] = [];
      let finalSources: SourceRef[] = [];
      let finalConfidence = "";
      let finalUnsupportedClaims: Array<{ claim: string; basis: string }> = [];
      let interrupted = false;
      let clarificationQuestion: string | null = null;
      let streamError: string | null = null;

      await streamMessage(
        submittedThreadId,
        userMessage,
        awaitingClarification,
        (event) => {
          if (event.type === "node_start") {
            if (event.node !== "retrieval_agent") {
              bufGraphEvents(prev => [
                ...prev.filter(graphEvent => !(graphEvent.node === event.node && graphEvent.status === "running")),
                { node: event.node, status: "running" },
              ]);
            }
            const newCards = toCards(nodeEventToCard(event.node, "running"));
            if (newCards.length > 0) {
              currentCards = [
                ...currentCards.filter(card => !newCards.some(newCard => newCard.id === card.id)),
                ...newCards,
              ];
              flushProgressMessage();
            }
          } else if (event.type === "node_done") {
            bufGraphEvents(prev => {
              const doneEntry = { node: event.node, status: "done" as const, state: event.state };
              let nextEvents: GraphNodeEvent[];
              if (event.node === "retrieval_agent") {
                nextEvents = [...prev, doneEntry];
              } else {
                const runningIdx = prev.findLastIndex(graphEvent => graphEvent.node === event.node && graphEvent.status === "running");
                if (runningIdx >= 0) {
                  nextEvents = [...prev.slice(0, runningIdx), doneEntry, ...prev.slice(runningIdx + 1)];
                } else {
                  const hasDone = prev.some(graphEvent => graphEvent.node === event.node && graphEvent.status === "done");
                  if (hasDone) {
                    nextEvents = prev.map(graphEvent => (
                      graphEvent.node === event.node && graphEvent.status === "done" ? doneEntry : graphEvent
                    ));
                  } else {
                    nextEvents = [...prev, doneEntry];
                  }
                }
              }
              if (event.node === "retrieve_decision" && event.state?.needs_retrieval) {
                nextEvents.push({ node: "retrieval_agent", status: "running" });
              }
              return nextEvents;
            });

            if (event.node === "synthesize" || event.node === "grade_answer" || event.node === "grade_docs") {
              pendingSubgraphDones.push({ node: event.node, state: event.state });
              if (event.node === "grade_docs") {
                const ordered = [
                  ...pendingSubgraphDones.filter(done => done.node === "grade_docs"),
                  ...pendingSubgraphDones.filter(done => done.node !== "grade_docs"),
                ];
                pendingSubgraphDones.length = 0;
                for (const { node: pNode, state: pState } of ordered) {
                  const pCards = toCards(nodeEventToCard(pNode, "done", pState));
                  const rIds = new Set([pNode, ...pCards.map(card => card.id)]);
                  currentCards = currentCards.filter(card => !(card.status === "running" && rIds.has(card.id)));
                  currentCards = [...currentCards, ...pCards];
                }
                flushProgressMessage();
              }
            } else {
              const newCards = toCards(nodeEventToCard(event.node, "done", event.state));
              const replaceIds = new Set([event.node, ...newCards.map(card => card.id)]);
              const runningIdx = currentCards.findIndex(
                card => card.status === "running" && replaceIds.has(card.id),
              );
              const filtered = currentCards.filter(card => {
                if (card.status === "running" && replaceIds.has(card.id)) return false;
                if (newCards.some(newCard => newCard.id === card.id)) return false;
                return true;
              });
              if (runningIdx >= 0 && newCards.length > 0) {
                const insertAt = Math.min(runningIdx, filtered.length);
                currentCards = [
                  ...filtered.slice(0, insertAt),
                  ...newCards,
                  ...filtered.slice(insertAt),
                ];
              } else {
                currentCards = [...filtered, ...newCards];
              }
              flushProgressMessage();
            }
          } else if (event.type === "interrupt") {
            interrupted = true;
            clarificationQuestion = event.question;
          } else if (event.type === "done") {
            finalAnswer = event.answer;
            finalChartData = event.chart_data ?? [];
            finalSources = event.sources ?? [];
            finalConfidence = event.confidence ?? "";
            finalUnsupportedClaims = event.unsupported_claims ?? [];
          } else if (event.type === "error") {
            streamError = event.detail;
          }
        },
      );

      setAwaitingClarification(false);

      const progressMsg: Message | null = currentCards.length > 0
        ? { role: "progress", content: "", cards: currentCards }
        : null;

      const base = [...next, ...(progressMsg ? [progressMsg] : [])];
      let updated = next as Message[];

      if (streamError) {
        setError(streamError);
        updated = base;
      } else if (interrupted && clarificationQuestion) {
        setAwaitingClarification(true);
        updated = [...base, { role: "assistant", content: clarificationQuestion }];
        setTypewriterIdx(updated.length - 1);
      } else if (finalAnswer) {
        updated = [
          ...base,
          {
            role: "assistant",
            content: finalAnswer,
            chartData: finalChartData,
            sources: finalSources,
            confidence: finalConfidence,
            unsupportedClaims: finalUnsupportedClaims,
          },
        ];
        setTypewriterIdx(updated.length - 1);
      } else {
        setError("No answer generated. Check LangSmith traces or try again.");
        updated = base;
      }

      bufMessages(() => updated);
      const label = next.find(message => message.role === "user")?.content ?? userMessage;
      saveThread(submittedThreadId, label.slice(0, 60), updated, streamBufferRef.current?.graphEvents ?? []);
      if (currentCards.length > 0) {
        const turnIndex = next.filter(message => message.role === "user").length - 1;
        saveProgress(submittedThreadId, turnIndex, currentCards);
      }
      setThreads(loadThreads());
    } catch (err) {
      if (threadIdRef.current === submittedThreadId) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      streamBufferRef.current = null;
      setStreamingThreadId(null);
      setStreamingLabel("");
      if (threadIdRef.current === submittedThreadId) {
        setLoading(false);
        inputRef.current?.focus();
      }
    }
  }, [
    awaitingClarification,
    graphEvents,
    input,
    inputRef,
    loading,
    messages,
    setAwaitingClarification,
    setError,
    setGraphEvents,
    setInput,
    setLoading,
    setMessages,
    setStreamingLabel,
    setStreamingThreadId,
    setThreads,
    setTypewriterIdx,
    streamBufferRef,
    threadId,
    threadIdRef,
  ]);

  return { handleSubmit };
}
