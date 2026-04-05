import { useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { ChatMessage } from "./chatHistory";

type ConversationLogProps = {
  chatHistory: ChatMessage[];
};

const AUTO_SCROLL_BOTTOM_THRESHOLD_PX = 60;

const normalizeStreamingText = (content: string): string => {
  // Chat history compression joins deltas with newlines; collapse them for sentence flow.
  return content.replace(/\s*\n+\s*/g, " ").replace(/\s{2,}/g, " ").trim();
};

const ConversationLog = ({ chatHistory }: ConversationLogProps) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const openFullscreenButtonRef = useRef<HTMLButtonElement | null>(null);
  const closeFullscreenButtonRef = useRef<HTMLButtonElement | null>(null);
  const previousFocusedElementRef = useRef<HTMLElement | null>(null);
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const fullscreenTitleId = "conversation-log-fullscreen-title";

  const visibleMessages = useMemo(
    () =>
      chatHistory.filter(
        (message) => message.role !== "system" && message.content.trim() !== "",
      ),
    [chatHistory],
  );

  useEffect(() => {
    if (!isAutoScrollEnabled) return;

    const container = containerRef.current;
    if (!container) return;

    container.scrollTop = container.scrollHeight;
  }, [visibleMessages, isAutoScrollEnabled]);

  useEffect(() => {
    if (!isFullscreen) return;

    previousFocusedElementRef.current = document.activeElement as HTMLElement | null;
    closeFullscreenButtonRef.current?.focus();

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsFullscreen(false);
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onEscape);
      previousFocusedElementRef.current?.focus();
    };
  }, [isFullscreen]);

  const onScroll = () => {
    const container = containerRef.current;
    if (!container) return;

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    setIsAutoScrollEnabled(
      distanceFromBottom <= AUTO_SCROLL_BOTTOM_THRESHOLD_PX,
    );
  };

  const conversationBody = (
    <div
      ref={containerRef}
      onScroll={onScroll}
      className={clsx(
        "overflow-y-auto rounded-md border border-gray/80",
        "bg-darkgray/70 backdrop-blur-sm p-3 md:p-4",
        isFullscreen ? "h-full" : "h-52 md:h-64",
      )}
    >
      {visibleMessages.length === 0 && (
        <div className="h-full flex items-center justify-center text-sm text-lightgray">
          Your conversation will appear here.
        </div>
      )}

      <div className="flex flex-col gap-2 md:gap-3">
        {visibleMessages.map((message, idx) => {
          const isAssistant = message.role === "assistant";
          const roleLabel = isAssistant ? "Assistant" : "User";
          const renderedText = normalizeStreamingText(message.content);

          return (
            <article
              key={`${idx}-${message.role}`}
              className={clsx(
                "rounded-md border px-3 py-2",
                isAssistant
                  ? "border-green/60 bg-green/10"
                  : "border-lightgray/60 bg-background/40",
              )}
            >
              <p
                className={clsx(
                  "text-[0.7rem] md:text-xs uppercase tracking-wider mb-1",
                  isAssistant ? "text-green" : "text-textgray",
                )}
              >
                {roleLabel}
              </p>
              <p className="break-words text-sm md:text-base leading-relaxed">
                {renderedText}
              </p>
            </article>
          );
        })}
      </div>
    </div>
  );

  return (
    <>
      {!isFullscreen && (
        <section className="w-full max-w-5xl px-3 md:px-0 mb-6" aria-label="Conversation log">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-sm md:text-base uppercase tracking-wide text-textgray">
              Conversation log
            </h2>
            <div className="flex items-center gap-3">
              {!isAutoScrollEnabled && (
                <span className="text-xs text-lightgray">auto-scroll paused</span>
              )}
              <button
                ref={openFullscreenButtonRef}
                type="button"
                onClick={() => setIsFullscreen(true)}
                className="text-xs md:text-sm uppercase tracking-wide border border-lightgray/70 px-2 py-1 rounded-sm text-offwhite hover:border-offwhite"
              >
                fullscreen
              </button>
            </div>
          </div>
          {conversationBody}
        </section>
      )}

      {isFullscreen && (
        <div className="fixed inset-0 z-40 bg-black/70 p-6 md:p-16">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby={fullscreenTitleId}
            className="w-full h-full flex flex-col"
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2
                id={fullscreenTitleId}
                className="text-sm md:text-base uppercase tracking-wide text-textgray"
              >
                Conversation log
              </h2>
              <div className="flex items-center gap-3">
                {!isAutoScrollEnabled && (
                  <span className="text-xs text-lightgray">auto-scroll paused</span>
                )}
                <button
                  ref={closeFullscreenButtonRef}
                  type="button"
                  onClick={() => setIsFullscreen(false)}
                  className="text-xs md:text-sm uppercase tracking-wide border border-lightgray/70 px-2 py-1 rounded-sm text-offwhite hover:border-offwhite"
                >
                  close
                </button>
              </div>
            </div>
            {conversationBody}
          </section>
        </div>
      )}
    </>
  );
};

export default ConversationLog;