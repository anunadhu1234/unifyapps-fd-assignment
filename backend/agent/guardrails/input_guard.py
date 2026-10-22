"""Input guard — deterministic checks on the raw user message, before any LLM call.

  * empty / over-long input is rejected;
  * prompt-injection attempts ("ignore previous instructions", "reveal your system
    prompt", fake <system> tags, role-play jailbreaks) are blocked outright — they
    never reach a model;
  * SQL pasted by the user is extracted, and a pasted write statement
    (DELETE / UPDATE / DROP …) is flagged so scope validation can refuse it.

Injection defence is layered: this guard catches the obvious attempts cheaply;
every prompt also wraps user text in <user_input> tags marked as untrusted data;
and whatever a model produces still has to pass the SQL validator and the
read-only database connection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("override_instructions", re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|your|the|any)\b"
        r"[^.\n]{0,25}\b(instructions?|rules?|prompts?|guardrails?|guidelines?|restrictions?|constraints?|policies)\b",
        re.I)),
    ("reveal_prompt", re.compile(
        r"\b(reveal|show|print|repeat|display|output|leak|tell me|what (is|are))\b[^.\n]{0,30}"
        r"\b(system|hidden|initial|original|developer)\s+(prompt|instructions?|message)", re.I)),
    ("role_hijack", re.compile(
        r"\b(you are now|from now on,? you|pretend (to be|you are)|act as (an? )?(unrestricted|uncensored|different|"
        r"evil|jailbroken|dba|database administrator|admin|root|developer)|roleplay as|role-play as)\b", re.I)),
    ("jailbreak_mode", re.compile(r"\b(developer mode|dan mode|do anything now|jailbreak|god mode|sudo mode)\b", re.I)),
    ("fake_delimiters", re.compile(
        r"(<\s*/?\s*(system|assistant|user_input|instructions?)\s*>|\[/?INST\]|<\|im_(start|end)\|>|"
        r"^\s*(system|assistant)\s*:|###\s*(system|instruction))", re.I | re.M)),
    ("new_instructions", re.compile(r"\b(new|updated|real|actual)\s+instructions?\s*:", re.I)),
]

_SQL_START = re.compile(
    r"(?is)(?:^|[\s:`(])((?:with\s+\w+\s+as\s*\(|select\s|insert\s+into\s|update\s+\w+\s+set\s|delete\s+from\s|"
    r"drop\s+(?:table|view|index|database|schema)\s|alter\s+table\s|truncate\s+(?:table\s+)?\w|"
    r"create\s+(?:table|view|index|temp|temporary|unique)\s|replace\s+into\s|merge\s+into\s|grant\s|revoke\s|"
    r"pragma\s|attach\s)[\s\S]*)")
_FENCE = re.compile(r"```(?:sql|sqlite)?\s*([\s\S]*?)```", re.I)
_WRITE_NODES = tuple(t for t in (getattr(exp, n, None) for n in (
    "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "AlterTable", "TruncateTable", "Command",
    "Pragma", "Attach", "Detach", "Grant", "Revoke")) if t is not None)
_WRITE_KEYWORDS = re.compile(
    r"(?i)^\s*(insert|update|delete|merge|drop|alter|truncate|create|replace|grant|revoke|pragma|attach|detach)\b")


@dataclass
class InputCheck:
    text: str
    blocked: bool = False
    reason: str | None = None  # empty | too_long | prompt_injection
    signals: list[str] = field(default_factory=list)
    user_sql: str | None = None
    user_sql_is_write: bool = False

    def as_dict(self) -> dict:
        return {"blocked": self.blocked, "reason": self.reason, "signals": self.signals,
                "user_sql": self.user_sql, "user_sql_is_write": self.user_sql_is_write}


def check_input(text: str, *, max_chars: int = 2000) -> InputCheck:
    cleaned = (text or "").replace("\x00", "").strip()
    result = InputCheck(cleaned)
    if not cleaned:
        result.blocked, result.reason = True, "empty"
        return result
    if len(cleaned) > max_chars:
        result.blocked, result.reason = True, "too_long"
        return result

    result.signals = [name for name, pattern in _INJECTION_PATTERNS if pattern.search(cleaned)]
    if result.signals:
        result.blocked, result.reason = True, "prompt_injection"

    result.user_sql = extract_sql(cleaned)
    if result.user_sql:
        result.user_sql_is_write = is_write_sql(result.user_sql)
    return result


def extract_sql(text: str) -> str | None:
    """SQL pasted into the message: a fenced block, else everything from the first SQL keyword."""
    fenced = _FENCE.search(text)
    if fenced and fenced.group(1).strip():
        return fenced.group(1).strip()
    m = _SQL_START.search(text)
    if not m:
        return None
    candidate = m.group(1).strip().rstrip("`").strip()
    # A bare "select" in prose ("select the best customers") is not SQL — but stacked
    # statements ("SELECT 1; DROP TABLE Orders") always are.
    if re.match(r"(?i)select\s", candidate) and not re.search(r"(?i)\bfrom\b", candidate) and ";" not in candidate:
        return None
    return candidate


def is_write_sql(sql: str) -> bool:
    """True when any statement in `sql` writes or changes schema (parse-based, keyword fallback)."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except Exception:
        return any(_WRITE_KEYWORDS.match(part) for part in sql.split(";"))
    return any(isinstance(s, _WRITE_NODES) or s.find(*_WRITE_NODES) is not None for s in statements)
