"""
flowback/llm.py — LLM integration

FlowBack works with any LLM provider supported by litellm.
Configure which model to use via environment variables in ~/.flowback/.env

─────────────────────────────────────────────────────────────────
CONFIGURATION
─────────────────────────────────────────────────────────────────

  LLM_MODEL      The model to use. See examples below.
  LLM_API_KEY    Your API key for the chosen provider.
  LLM_API_BASE   (Optional) Custom API base URL. Required for Ollama.

─────────────────────────────────────────────────────────────────
PROVIDER EXAMPLES  (~/.flowback/.env)
─────────────────────────────────────────────────────────────────

  Google Gemini (default — free tier available)
  ┌──────────────────────────────────────────────────────────┐
  │ LLM_MODEL=gemini/gemini-2.5-flash                        │
  │ LLM_API_KEY=your_gemini_key                              │
  │ → Get key: https://aistudio.google.com/app/apikey        │
  └──────────────────────────────────────────────────────────┘

  OpenAI
  ┌──────────────────────────────────────────────────────────┐
  │ LLM_MODEL=gpt-4o                                         │
  │ LLM_API_KEY=your_openai_key                              │
  │ → Get key: https://platform.openai.com/api-keys          │
  └──────────────────────────────────────────────────────────┘

  Anthropic Claude
  ┌──────────────────────────────────────────────────────────┐
  │ LLM_MODEL=claude-3-5-sonnet-20241022                     │
  │ LLM_API_KEY=your_anthropic_key                           │
  │ → Get key: https://console.anthropic.com/                │
  └──────────────────────────────────────────────────────────┘

  Groq (fast + free tier)
  ┌──────────────────────────────────────────────────────────┐
  │ LLM_MODEL=groq/llama-3.1-70b-versatile                   │
  │ LLM_API_KEY=your_groq_key                                │
  │ → Get key: https://console.groq.com/                     │
  └──────────────────────────────────────────────────────────┘

  Ollama — fully local, no API key needed
  ┌──────────────────────────────────────────────────────────┐
  │ LLM_MODEL=ollama/llama3                                  │
  │ LLM_API_BASE=http://localhost:11434                      │
  │ → Install: https://ollama.com                            │
  └──────────────────────────────────────────────────────────┘

  Any other provider supported by litellm:
  → Full list: https://docs.litellm.ai/docs/providers
─────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from litellm import completion

# Load ~/.flowback/.env first, then fallback to cwd .env
load_dotenv(Path.home() / ".flowback" / ".env")
load_dotenv()

# ── Model config ──────────────────────────────────────────────────────────────
_MODEL: str = os.environ.get("LLM_MODEL", "gemini/gemini-2.5-flash")

# LLM_API_KEY is the standard var; GEMINI_API_KEY kept for backwards compat
_API_KEY: Optional[str] = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")

# Optional custom base URL (required for Ollama, useful for proxies)
_API_BASE: Optional[str] = os.environ.get("LLM_API_BASE")

# ── Prompts ───────────────────────────────────────────────────────────────────

BRIEFING_PROMPT = """You are a developer productivity assistant.
Given a snapshot of recently modified files and an optional developer note,
analyze the context and return a JSON briefing.

Return ONLY valid JSON with this exact structure:
{
  "goal": "One sentence describing what the developer was trying to achieve",
  "stuck_point": "One sentence describing where they likely paused or got stuck",
  "next_steps": [
    "Step 1 description",
    "Step 2 description",
    "Step 3 description"
  ],
  "files_changed": ["file1.py", "file2.js"],
  "tags": ["short-tag", "another-tag"]
}

For tags: generate 2-5 short lowercase hyphenated labels that capture the core problem areas
(e.g. "cors-issue", "auth-token", "file-upload", "api-integration", "state-management").
Tags should be specific enough to be meaningful if they recur across sessions.

Be specific and technical. Base your analysis on the actual file contents.
Do not include markdown code fences or any text outside the JSON object."""

ERROR_PROMPT = """You are a developer productivity assistant specializing in error analysis.
Given an error message, return a JSON analysis.

Return ONLY valid JSON with this exact structure:
{
  "fingerprint": "short normalized error identifier, no line numbers or file paths, lowercase hyphenated (e.g. 'typeerror-cannot-read-undefined', 'modulenotfounderror-missing-module')",
  "error_type": "The error class or category (e.g. TypeError, CORS, 401 Unauthorized)",
  "root_cause": "One clear sentence explaining why this error happens",
  "solution": [
    "Concrete step 1 to fix it",
    "Concrete step 2 to fix it",
    "Concrete step 3 to fix it"
  ],
  "prevention": "One actionable sentence on how to avoid hitting this error again in the future",
  "tags": ["short-tag-1", "short-tag-2"]
}

For fingerprint: strip all line numbers, file paths, memory addresses, and specific values.
Two occurrences of the same logical error must produce the same fingerprint.
Do not include markdown code fences or any text outside the JSON object."""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _call(prompt: str) -> str:
    """Send a prompt to the configured LLM and return the response text."""
    kwargs: dict = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    if _API_KEY:
        kwargs["api_key"] = _API_KEY
    if _API_BASE:
        kwargs["api_base"] = _API_BASE

    try:
        response = completion(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(
            f"LLM call failed (model: {_MODEL}).\n"
            f"Check your LLM_MODEL and LLM_API_KEY in ~/.flowback/.env\n"
            f"Error: {e}"
        ) from e


def _parse_json(text: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def _build_briefing_prompt(
    user_note: Optional[str],
    file_contents: dict[str, str],
    files_changed: list[str],
) -> str:
    parts = [BRIEFING_PROMPT, "\n\n---\n"]
    if user_note:
        parts.append(f"## Developer Note\n{user_note}\n\n")
    if files_changed:
        parts.append("## Files Changed\n" + "\n".join(f"- {f}" for f in files_changed) + "\n\n")
    if file_contents:
        parts.append("## File Contents\n")
        for path, content in file_contents.items():
            parts.append(f"\n### {path}\n```\n{content}\n```\n")
    parts.append("\n---\nReturn the JSON briefing now:")
    return "".join(parts)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_briefing(
    user_note: Optional[str],
    file_contents: dict[str, str],
    files_changed: list[str],
) -> tuple[dict, str]:
    """
    Generate an AI briefing for a project snapshot.
    Returns (parsed_briefing_dict, raw_response_text).
    """
    prompt = _build_briefing_prompt(user_note, file_contents, files_changed)
    raw = _call(prompt)

    try:
        briefing = _parse_json(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    briefing.setdefault("goal", "")
    briefing.setdefault("stuck_point", "")
    briefing.setdefault("next_steps", [])
    briefing.setdefault("files_changed", files_changed)
    briefing.setdefault("tags", [])

    return briefing, raw


def analyze_error(raw_error: str, occurrence_count: int = 0) -> tuple[dict, str]:
    """
    Analyze an error message.
    Returns (parsed_analysis_dict, raw_response_text).
    """
    loop_note = ""
    if occurrence_count >= 2:
        loop_note = (
            f"\n\nIMPORTANT: This error has occurred {occurrence_count + 1} times already. "
            "In the 'prevention' field, give specific advice on breaking this recurring pattern, "
            "not just a generic fix tip."
        )

    prompt = (
        f"{ERROR_PROMPT}{loop_note}\n\n---\n"
        f"## Error\n```\n{raw_error}\n```\n---\n"
        "Return the JSON analysis now:"
    )
    raw = _call(prompt)

    try:
        analysis = _parse_json(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    analysis.setdefault("fingerprint", "unknown-error")
    analysis.setdefault("error_type", "Unknown")
    analysis.setdefault("root_cause", "")
    analysis.setdefault("solution", [])
    analysis.setdefault("prevention", "")
    analysis.setdefault("tags", [])

    return analysis, raw
