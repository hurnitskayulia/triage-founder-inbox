"""Thin, swappable LLM backend.

Uses the locally authenticated `claude` CLI in headless print mode, so the
pipeline needs no API key to run inside a Claude Code environment. To run it
somewhere else, replace `complete()`'s body with a direct Anthropic API call
(e.g. via the `anthropic` SDK) using ANTHROPIC_API_KEY - nothing else in the
pipeline needs to change, since every caller only depends on `complete_json`.
"""
import json
import re
import subprocess

DEFAULT_MODEL = "claude-sonnet-5"
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


class LLMError(RuntimeError):
    pass


def complete(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL, timeout: int = 90) -> str:
    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--model", model,
                "--append-system-prompt", system_prompt,
                "--output-format", "text",
            ],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as e:
        raise LLMError("`claude` CLI not found on PATH; cannot reach the LLM backend") from e
    except subprocess.TimeoutExpired as e:
        raise LLMError(f"LLM call timed out after {timeout}s") from e

    if result.returncode != 0:
        raise LLMError(f"claude CLI exited {result.returncode}: {result.stderr.strip()[:500]}")
    return result.stdout.strip()


def complete_json(prompt: str, system_prompt: str, model: str = DEFAULT_MODEL,
                   timeout: int = 90, retries: int = 1) -> dict:
    last_err = None
    for _ in range(retries + 1):
        try:
            raw = complete(prompt, system_prompt, model=model, timeout=timeout)
            cleaned = _FENCE_RE.sub("", raw).strip()
            return json.loads(cleaned)
        except (LLMError, json.JSONDecodeError) as e:
            last_err = e
    raise LLMError(f"LLM did not return parseable JSON after {retries + 1} attempt(s): {last_err}")
