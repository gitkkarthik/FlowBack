import json
import os
import re
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
_model = genai.GenerativeModel("gemini-2.5-flash")

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


def _build_prompt(
    user_note: Optional[str],
    file_contents: dict[str, str],
    files_changed: list[str],
) -> str:
    parts = [SYSTEM_PROMPT, "\n\n---\n"]

    if user_note:
        parts.append(f"## Developer Note\n{user_note}\n\n")

    if files_changed:
        parts.append(f"## Files Changed\n" + "\n".join(f"- {f}" for f in files_changed) + "\n\n")

    if file_contents:
        parts.append("## File Contents\n")
        for path, content in file_contents.items():
            parts.append(f"\n### {path}\n```\n{content}\n```\n")

    parts.append("\n---\nReturn the JSON briefing now:")
    return "".join(parts)


def _parse_response(text: str) -> dict:
    # Strip markdown fences if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())


def generate_briefing(
    user_note: Optional[str],
    file_contents: dict[str, str],
    files_changed: list[str],
) -> tuple[dict, str]:
    """
    Returns (parsed_briefing_dict, raw_response_text).
    Raises on API or parse errors.
    """
    prompt = _build_prompt(user_note, file_contents, files_changed)

    try:
        response = _model.generate_content(prompt)
        raw = response.text
    except Exception as e:
        raise RuntimeError(f"Gemini API call failed: {e}") from e

    try:
        briefing = _parse_response(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\n\nRaw response:\n{raw}") from e

    # Validate required keys with defaults
    briefing.setdefault("goal", "")
    briefing.setdefault("stuck_point", "")
    briefing.setdefault("next_steps", [])
    briefing.setdefault("files_changed", files_changed)

    return briefing, raw
