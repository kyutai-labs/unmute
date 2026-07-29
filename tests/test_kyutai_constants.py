import pytest

from unmute import kyutai_constants


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("true", True),
        ("FALSE", False),
    ],
)
def test_optional_bool_env_parses_supported_values(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str | None,
    expected: bool | None,
):
    if raw_value is None:
        monkeypatch.delenv("KYUTAI_LLM_ENABLE_THINKING", raising=False)
    else:
        monkeypatch.setenv("KYUTAI_LLM_ENABLE_THINKING", raw_value)

    value = kyutai_constants.optional_bool_env("KYUTAI_LLM_ENABLE_THINKING")

    assert value is expected


def test_optional_bool_env_rejects_unknown_values(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("KYUTAI_LLM_ENABLE_THINKING", "sometimes")

    with pytest.raises(ValueError, match="KYUTAI_LLM_ENABLE_THINKING"):
        kyutai_constants.optional_bool_env("KYUTAI_LLM_ENABLE_THINKING")
