"""Check the AWS Bedrock setup: the bearer token works and both configured models answer.

Usage (from backend/):  python scripts/check_llm.py
"""

from __future__ import annotations

import sys

from agent.llm_client import LLMNotConfiguredError, build_chat_model
from utils.config import get_settings


def main() -> int:
    s = get_settings()
    print(f"Bedrock region: {s.aws_region}")
    ok = True
    for role, model in (("fast", s.llm_model_fast), ("main", s.llm_model_main)):
        try:
            reply = build_chat_model(model, s).invoke("Reply with exactly: pong")
        except LLMNotConfiguredError as exc:
            print(f"  [skip] {exc}")
            return 1
        except Exception as exc:
            ok = False
            print(f"  [FAIL] {role:<4} {model}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        usage = reply.usage_metadata or {}
        print(f"  [ok]   {role:<4} {model}: {reply.text!r} "
              f"({usage.get('input_tokens')} in / {usage.get('output_tokens')} out tokens)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
