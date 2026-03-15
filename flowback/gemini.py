import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai

# Load .env from ~/.flowback/ first, then fallback to cwd
load_dotenv(Path.home() / ".flowback" / ".env")
load_dotenv()

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are a developer productivity assistant.
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


def _build_prompt(
    user_note: Optional[str],
    file_contents: dict[str, str],
    files_changed: list[str],
) -> str:
    parts = [SYSTEM_PROMPT, "\n\n---\n"]

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


def _parse_response(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def generate_briefing(
    user_note: Optional[str],
    file_contents: dict[str, str],
    files_changed: list[str],
) -> tuple[dict, str]:
    prompt = _build_prompt(user_note, file_contents, files_changed)

    try:
        response = _client.models.generate_content(model=_MODEL, contents=prompt)
        raw = response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}") from e

    try:
        briefing = _parse_response(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    briefing.setdefault("goal", "")
    briefing.setdefault("stuck_point", "")
    briefing.setdefault("next_steps", [])
    briefing.setdefault("files_changed", files_changed)
    briefing.setdefault("tags", [])

    return briefing, raw


def analyze_error(raw_error: str, occurrence_count: int = 0) -> tuple[dict, str]:
    loop_note = ""
    if occurrence_count >= 2:
        loop_note = (
            f"\n\nIMPORTANT: This error has occurred {occurrence_count + 1} times already. "
            "In the 'prevention' field, give specific advice on breaking this recurring pattern, "
            "not just a generic fix tip."
        )

    prompt = f"{ERROR_PROMPT}{loop_note}\n\n---\n## Error\n```\n{raw_error}\n```\n---\nReturn the JSON analysis now:"

    try:
        response = _client.models.generate_content(model=_MODEL, contents=prompt)
        raw = response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}") from e

    try:
        analysis = _parse_response(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    analysis.setdefault("fingerprint", "unknown-error")
    analysis.setdefault("error_type", "Unknown")
    analysis.setdefault("root_cause", "")
    analysis.setdefault("solution", [])
    analysis.setdefault("prevention", "")
    analysis.setdefault("tags", [])

    return analysis, raw
