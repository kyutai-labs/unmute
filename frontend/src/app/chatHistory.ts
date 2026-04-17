export type ChatRole =
  | "user"
  | "assistant"
  | "system"
  | "llm_raw"
  | "llm_reasoning"
  | "llm_plan"
  | "llm_speech"
  | "llm_exec";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

/** If there are multiple messages from the same role in a row, combine them into one message */
export const compressChatHistory = (
  chatHistory: ChatMessage[]
): ChatMessage[] => {
  const compressed: ChatMessage[] = [];
  for (const message of chatHistory) {
    if (
      compressed.length > 0 &&
      compressed[compressed.length - 1].role === message.role
    ) {
      // Raw LLM tokens already include their own spacing; concatenate verbatim.
      const separator = message.role === "llm_raw" ? "" : "\n";
      compressed[compressed.length - 1].content +=
        `${separator}${message.content}`;
    } else {
      compressed.push({ ...message });
    }
  }
  return compressed;
};
