"use client";

import { useCallback, useEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from "react";
import type { ProgressCardData } from "@/components/ProgressCard";
import { createThread, deleteThread, fetchProgress, fetchThreadHistory, fetchThreads } from "@/lib/api";
import { enrichMessages } from "@/lib/messageSources";
import { ACTIVE_THREAD_KEY, loadThreads, saveThread, type StoredThread } from "@/lib/threadStorage";
import type { Message } from "@/types/chat";
import type { GraphNodeEvent } from "@/types/graph";

export interface StreamBuffer {
  threadId: string;
  messages: Message[];
  graphEvents: GraphNodeEvent[];
}

interface UseThreadsOptions {
  inputRef: RefObject<HTMLInputElement | null>;
  streamBufferRef: RefObject<StreamBuffer | null>;
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setGraphEvents: Dispatch<SetStateAction<GraphNodeEvent[]>>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setTypewriterIdx: Dispatch<SetStateAction<number | null>>;
  setAwaitingClarification: Dispatch<SetStateAction<boolean>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setMobileSidebarOpen: Dispatch<SetStateAction<boolean>>;
}

export function useThreads({
  inputRef,
  streamBufferRef,
  setMessages,
  setGraphEvents,
  setLoading,
  setTypewriterIdx,
  setAwaitingClarification,
  setError,
  setMobileSidebarOpen,
}: UseThreadsOptions) {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState(true);
  const [threads, setThreads] = useState<StoredThread[]>([]);
  const threadIdRef = useRef<string | null>(null);

  useEffect(() => {
    const localThreads = loadThreads();
    setThreads(localThreads);

    fetchThreads().then(backendThreads => {
      if (backendThreads.length === 0) return;
      // Re-read localStorage at resolve time to avoid stale-closure races.
      const freshLocalMap = new Map(loadThreads().map(t => [t.id, t]));
      const merged: StoredThread[] = backendThreads.map(bt => {
        const local = freshLocalMap.get(bt.id);
        return {
          id: bt.id,
          label: bt.label || local?.label || "Untitled",
          updatedAt: bt.updated_at ? new Date(bt.updated_at).getTime() : (local?.updatedAt ?? 0),
          messages: local?.messages ?? [],
          graphEvents: local?.graphEvents,
        };
      });
      setThreads(merged);
    });

    const savedThreadId = sessionStorage.getItem(ACTIVE_THREAD_KEY);
    if (savedThreadId) {
      setThreadId(savedThreadId);
      const savedThread = localThreads.find(t => t.id === savedThreadId);
      if (savedThread && savedThread.messages.length > 0) {
        setMessages(enrichMessages(savedThread.messages));
        setGraphEvents(savedThread.graphEvents ?? []);
      }
    } else {
      createThread()
        .then(id => {
          setThreadId(id);
          sessionStorage.setItem(ACTIVE_THREAD_KEY, id);
        })
        .catch(() => {
          setBackendOk(false);
          setError("Cannot connect to backend. Run: uv run uvicorn app:app --reload");
        });
    }
  }, [setError, setGraphEvents, setMessages]);

  useEffect(() => {
    threadIdRef.current = threadId;
  }, [threadId]);

  const refreshThreads = useCallback(() => {
    setThreads(loadThreads());
  }, []);

  const handleReturnToActive = useCallback(() => {
    if (!streamBufferRef.current) return;
    const { threadId: tid, messages: msgs, graphEvents: evts } = streamBufferRef.current;
    setThreadId(tid);
    sessionStorage.setItem(ACTIVE_THREAD_KEY, tid);
    setMessages(msgs);
    setGraphEvents(evts);
    setLoading(true);
  }, [setGraphEvents, setLoading, setMessages, streamBufferRef]);

  const handleNewConversation = useCallback(async () => {
    try {
      const id = await createThread();
      setThreadId(id);
      sessionStorage.setItem(ACTIVE_THREAD_KEY, id);
      setMessages([]);
      setGraphEvents([]);
      setTypewriterIdx(null);
      setAwaitingClarification(false);
      setError(null);
      setBackendOk(true);
      inputRef.current?.focus();
    } catch {
      setError("Cannot connect to backend.");
    }
  }, [inputRef, setAwaitingClarification, setError, setGraphEvents, setMessages, setTypewriterIdx]);

  const handleSelectThread = useCallback(async (t: StoredThread) => {
    if (t.id === streamBufferRef.current?.threadId) {
      handleReturnToActive();
      return;
    }

    if (streamBufferRef.current) {
      setLoading(false);
    }

    setMobileSidebarOpen(false);
    setThreadId(t.id);
    sessionStorage.setItem(ACTIVE_THREAD_KEY, t.id);
    setGraphEvents(t.graphEvents ?? []);
    setTypewriterIdx(null);
    setAwaitingClarification(false);
    setError(null);

    if (t.messages.length > 0) {
      setMessages(enrichMessages(t.messages));
    } else {
      const [history, progressTurns] = await Promise.all([
        fetchThreadHistory(t.id),
        fetchProgress(t.id),
      ]);
      const progressMap = new Map(progressTurns.map(p => [p.turn_index, p.cards as ProgressCardData[]]));
      const msgs: Message[] = [];
      let turnIdx = 0;
      for (const m of history) {
        msgs.push({ role: m.role as Message["role"], content: m.content });
        if (m.role === "user") {
          const cards = progressMap.get(turnIdx);
          if (cards && cards.length > 0) {
            msgs.push({ role: "progress", content: "", cards });
          }
          turnIdx++;
        }
      }
      setMessages(enrichMessages(msgs));
      if (msgs.length > 0) {
        saveThread(t.id, t.label, msgs, []);
        setThreads(loadThreads());
      }
    }

    inputRef.current?.focus();
  }, [
    handleReturnToActive,
    inputRef,
    setAwaitingClarification,
    setError,
    setGraphEvents,
    setLoading,
    setMessages,
    setMobileSidebarOpen,
    setTypewriterIdx,
    streamBufferRef,
  ]);

  const handleDeleteThread = useCallback(async (id: string) => {
    setThreads(prev => prev.filter(t => t.id !== id));
    const remaining = loadThreads().filter(t => t.id !== id);
    localStorage.setItem("chat_threads", JSON.stringify(remaining));

    if (id === threadId) {
      setMessages([]);
      setGraphEvents([]);
      setTypewriterIdx(null);
      setAwaitingClarification(false);
      setError(null);
      sessionStorage.removeItem(ACTIVE_THREAD_KEY);
      try {
        const newId = await createThread();
        setThreadId(newId);
        sessionStorage.setItem(ACTIVE_THREAD_KEY, newId);
      } catch {
        // Keep the UI usable with an empty local thread if the backend is offline.
      }
    }

    deleteThread(id).catch(() => {});
  }, [
    setAwaitingClarification,
    setError,
    setGraphEvents,
    setMessages,
    setTypewriterIdx,
    threadId,
  ]);

  return {
    threadId,
    threadIdRef,
    backendOk,
    threads,
    setThreads,
    refreshThreads,
    handleReturnToActive,
    handleNewConversation,
    handleSelectThread,
    handleDeleteThread,
  };
}
