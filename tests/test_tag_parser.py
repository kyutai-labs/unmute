import pytest

from unmute.llm.unmute_tag_parser import LLMTagPrinter, extract_speech_tags


async def make_iterator(s: str):
    for part in s.split("|"):
        yield part


async def run(s: str) -> str:
    return "".join([x async for x in extract_speech_tags(make_iterator(s))])


@pytest.mark.asyncio
async def test_discards_reasoning_plan_exec():
    src = "<reasoning>think</reasoning><plan>[{}]</plan><speech>hi</speech><exec>{}</exec>"
    assert await run(src) == "hi"


@pytest.mark.asyncio
async def test_tag_split_across_deltas_open():
    assert await run("<spee|ch>|hello|</speech>") == "hello"


@pytest.mark.asyncio
async def test_tag_split_across_deltas_close():
    assert await run("<speech>hi|</spe|ech>") == "hi"


@pytest.mark.asyncio
async def test_single_char_deltas():
    s = "<speech>abc</speech>"
    chunked = "|".join(list(s))
    assert await run(chunked) == "abc"


@pytest.mark.asyncio
async def test_multiple_speech_blocks():
    src = "<reasoning>r</reasoning><speech>one </speech><plan>p</plan><speech>two</speech>"
    assert await run(src) == "one two"


@pytest.mark.asyncio
async def test_literal_lt_inside_speech():
    assert await run("<speech>a < b</speech>") == "a < b"


@pytest.mark.asyncio
async def test_unclosed_speech_flushes_on_eos():
    assert await run("<speech>partial") == "partial"


@pytest.mark.asyncio
async def test_unclosed_non_speech_discarded_on_eos():
    assert await run("<reasoning>hmm") == ""


@pytest.mark.asyncio
async def test_empty_speech_block():
    assert await run("<speech></speech>") == ""


@pytest.mark.asyncio
async def test_nothing_outside_speech_is_emitted():
    assert await run("garbage before <speech>ok</speech> trailing") == "ok"


@pytest.mark.asyncio
async def test_chunk_yields_are_non_empty_strings():
    out = [
        x
        async for x in extract_speech_tags(
            make_iterator("<speech>hello world</speech>")
        )
    ]
    assert all(isinstance(x, str) and x != "" for x in out)
    assert "".join(out) == "hello world"


@pytest.mark.asyncio
async def test_all_possible_split_points_stable():
    src = "<reasoning>r</reasoning><speech>hello</speech><plan>p</plan><speech> world</speech>"
    expected = "hello world"
    for cut in range(len(src) + 1):

        async def gen(a: str = src[:cut], b: str = src[cut:]):
            if a:
                yield a
            if b:
                yield b

        got = "".join([x async for x in extract_speech_tags(gen())])
        assert got == expected, f"mismatch at cut={cut}: got {got!r}"


# --- LLMTagPrinter tests ---


def feed_all(s: str, split: str = "|") -> list[tuple[str, str]]:
    p = LLMTagPrinter()
    results: list[tuple[str, str]] = []
    for chunk in s.split(split):
        results.extend(p.feed(chunk))
    results.extend(p.flush())
    return results


def test_llm_tag_printer_all_four_tag_types():
    src = "<reasoning>r1</reasoning><plan>[{}]</plan><speech>hi</speech><exec>{}</exec>"
    assert feed_all(src) == [
        ("reasoning", "r1"),
        ("plan", "[{}]"),
        ("speech", "hi"),
        ("exec", "{}"),
    ]


def test_llm_tag_printer_split_across_feeds_open():
    assert feed_all("<reas|oning>|abc|</reasoning>") == [("reasoning", "abc")]


def test_llm_tag_printer_split_across_feeds_close():
    assert feed_all("<plan>abc|</pla|n>") == [("plan", "abc")]


def test_llm_tag_printer_single_char_feeds():
    src = "<exec>run</exec>"
    assert feed_all("|".join(list(src))) == [("exec", "run")]


def test_llm_tag_printer_discards_content_outside_tags():
    src = "garbage <speech>kept</speech> more garbage <plan>also kept</plan>"
    assert feed_all(src) == [("speech", "kept"), ("plan", "also kept")]


def test_llm_tag_printer_empty_body_not_yielded():
    assert feed_all("<speech></speech><plan></plan>") == []


def test_llm_tag_printer_unclosed_tag_discarded_on_flush():
    p = LLMTagPrinter()
    assert p.feed("<reasoning>partial") == []
    assert p.flush() == []


def test_llm_tag_printer_literal_lt_inside_tag_preserved():
    assert feed_all("<plan>a < b</plan>") == [("plan", "a < b")]


def test_llm_tag_printer_all_split_points_stable():
    src = (
        "<reasoning>r</reasoning>"
        "<speech>hi</speech>"
        "<plan>p</plan>"
        "<exec>e</exec>"
    )
    expected = [("reasoning", "r"), ("speech", "hi"), ("plan", "p"), ("exec", "e")]
    for cut in range(len(src) + 1):
        p = LLMTagPrinter()
        got = p.feed(src[:cut]) + p.feed(src[cut:]) + p.flush()
        assert got == expected, f"mismatch at cut={cut}: {got!r}"


def test_llm_tag_printer_reset_between_responses():
    p = LLMTagPrinter()
    assert p.feed("<speech>one</speech>") == [("speech", "one")]
    assert p.feed("<speech>two</speech>") == [("speech", "two")]
