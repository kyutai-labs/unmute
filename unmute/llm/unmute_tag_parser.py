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
