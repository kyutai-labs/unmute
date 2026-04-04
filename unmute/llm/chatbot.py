from logging import getLogger
from typing import Any, Literal

from unmute.llm.llm_utils import preprocess_messages_for_llm
from unmute.llm.system_prompt import ConstantInstructions, Instructions

ConversationState = Literal["waiting_for_user", "user_speaking", "bot_speaking"]

logger = getLogger(__name__)


class Chatbot:
    def __init__(self):
        # It's actually a list of ChatCompletionStreamRequestMessagesTypedDict but then
        # it's really difficult to convince Python you're passing in the right type
        self.chat_history: list[dict[Any, Any]] = [
            {"role": "system", "content": ConstantInstructions().make_system_prompt()}
        ]
        self._instructions: Instructions | None = None

    def conversation_state(self) -> ConversationState:
        if not self.chat_history:
            return "waiting_for_user"

        last_message = self.chat_history[-1]
        if last_message["role"] == "assistant":
            return "bot_speaking"
        elif last_message["role"] == "user":
            if last_message["content"].strip() != "":
                return "user_speaking"
            else:
                # Or do we want "user_speaking" here?
                return "waiting_for_user"
        elif last_message["role"] == "system":
            return "waiting_for_user"
        else:
            raise RuntimeError(f"Unknown role: {last_message['role']}")

    async def add_chat_message_delta(
        self,
        delta: str,
        role: Literal["user", "assistant"],
        generating_message_i: int | None = None,  # Avoid race conditions
    ) -> bool:
        """Add a partial message to the chat history, adding spaces if necessary.

        Returns:
            True if the message is a new message, False if it is a continuation of
            the last message.
        """
        if (
            generating_message_i is not None
            and len(self.chat_history) > generating_message_i
        ):
            logger.warning(
                f"Tried to add {delta=} {role=} "
                f"but {generating_message_i=} didn't match"
            )
            return False

        if not self.chat_history or self.chat_history[-1]["role"] != role:
            self.chat_history.append({"role": role, "content": delta})
            return True
        else:
            last_message: str = self.chat_history[-1]["content"]

            # Add a space if necessary
            needs_space_left = last_message != "" and not last_message[-1].isspace()
            needs_space_right = delta != "" and not delta[0].isspace()

            if needs_space_left and needs_space_right:
                delta = " " + delta

            self.chat_history[-1]["content"] += delta
            return last_message == ""  # new message if `last_message` was empty

    def preprocessed_messages(self):
        messages = self.chat_history

        messages = preprocess_messages_for_llm(messages)
        return messages

    def set_instructions(self, instructions: Instructions):
        # Note that make_system_prompt() might not be deterministic, so we run it only
        # once and save the result. We still keep self._instructions because it's used
        # to check whether initial instructions have been set.
        self._update_system_prompt(instructions.make_system_prompt())
        self._instructions = instructions

    def _update_system_prompt(self, system_prompt: str):
        self.chat_history[0] = {"role": "system", "content": system_prompt}

    def get_system_prompt(self) -> str:
        assert len(self.chat_history) > 0
        assert self.chat_history[0]["role"] == "system"
        return self.chat_history[0]["content"]

    def get_instructions(self) -> Instructions | None:
        return self._instructions

    def last_message(self, role: str) -> str | None:
        valid_messages = [
            message
            for message in self.chat_history
            if message["role"] == role and message["content"].strip() != ""
        ]
        if valid_messages:
            return valid_messages[-1]["content"]
        else:
            return None
