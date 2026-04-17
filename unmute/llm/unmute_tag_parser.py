from collections.abc import AsyncIterator

_OPEN_TAGS = ("<speech>", "<reasoning>", "<plan>", "<exec>")
_CLOSE_TAGS = ("</speech>", "</reasoning>", "</plan>", "</exec>")
_MAX_TAG_LEN = max(len(t) for t in _OPEN_TAGS + _CLOSE_TAGS)


def _is_prefix_of_any(s: str, candidates: tuple[str, ...]) -> bool:
    return any(c.startswith(s) for c in candidates)


async def extract_speech_tags(
    iterator: AsyncIterator[str],
    *,
    emit_chunk_size: int = 32,
) -> AsyncIterator[str]:
    """Yield only text contained inside <speech>...</speech> tags.

    Handles tag boundaries split across deltas. Multiple <speech> blocks are
    yielded in order. Unclosed <speech> at EOS is flushed as best-effort.
    """
    in_speech = False
    pending = ""  # buffered '<...' that might become a tag
    out = ""  # outgoing speech chars, flushed in chunks

    async for delta in iterator:
        i = 0
        while i < len(delta):
            ch = delta[i]

            if pending:
                pending += ch
                i += 1
                candidates = _CLOSE_TAGS if in_speech else (_OPEN_TAGS + _CLOSE_TAGS)
                if pending in candidates:
                    if pending == "<speech>":
                        in_speech = True
                    elif pending == "</speech>":
                        in_speech = False
                        if out:
                            yield out
                            out = ""
                    pending = ""
                elif _is_prefix_of_any(pending, candidates):
                    continue
                else:
                    if in_speech:
                        out += pending
                        if len(out) >= emit_chunk_size:
                            yield out
                            out = ""
                    pending = ""
                continue

            if ch == "<":
                pending = "<"
                i += 1
                continue

            if in_speech:
                out += ch
                if len(out) >= emit_chunk_size:
                    yield out
                    out = ""
            i += 1

    # EOS flush
    if in_speech:
        if pending:
            out += pending
        if out:
            yield out


_TAG_NAMES: tuple[str, ...] = tuple(t[1:-1] for t in _OPEN_TAGS)


class LLMTagPrinter:
    """Synchronous incremental parser that yields complete closed tag blocks.

    Call feed(delta) per incoming chunk; returns a (possibly empty) list of
    (tag_name, content) pairs for tags closed within this feed.
    flush() at end-of-response discards any unclosed buffer.

    Content outside any recognized tag is silently discarded. Empty tag
    bodies are not yielded.
    """

    __slots__ = ("_current_tag", "_content_buf", "_pending")

    def __init__(self) -> None:
        self._current_tag: str | None = None
        self._content_buf: str = ""
        self._pending: str = ""

    def feed(self, delta: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        i = 0
        while i < len(delta):
            ch = delta[i]

            if self._pending:
                self._pending += ch
                i += 1
                if self._current_tag is None:
                    candidates: tuple[str, ...] = _OPEN_TAGS + _CLOSE_TAGS
                else:
                    candidates = (f"</{self._current_tag}>",)
                if self._pending in candidates:
                    if self._current_tag is None:
                        self._current_tag = self._pending[1:-1]
                        self._content_buf = ""
                    else:
                        if self._content_buf:
                            out.append((self._current_tag, self._content_buf))
                        self._current_tag = None
                        self._content_buf = ""
                    self._pending = ""
                elif _is_prefix_of_any(self._pending, candidates):
                    continue
                else:
                    if self._current_tag is not None:
                        self._content_buf += self._pending
                    self._pending = ""
                continue

            if ch == "<":
                self._pending = "<"
                i += 1
                continue

            if self._current_tag is not None:
                self._content_buf += ch
            i += 1

        return out

    def flush(self) -> list[tuple[str, str]]:
        self._current_tag = None
        self._content_buf = ""
        self._pending = ""
        return []
