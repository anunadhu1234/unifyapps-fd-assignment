"""Ask the agent from the terminal — handy for quick checks without the web UI.

Usage (from backend/):
    python scripts/ask.py "Show all employees hired after January 2024."
    python scripts/ask.py --thread demo "Show all customers." "Only those from California."
    python scripts/ask.py --dev "Top 5 customers by revenue"        # also print trace + LLM calls
    python scripts/ask.py --no-execute "List products"               # SQL only
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid

from agent.supervisor.supervisor import SQLAgent


def show(response: dict, dev: bool) -> None:
    print(f"\n[{response['type']}] {response['message']}")
    if response.get("sql"):
        print("\nSQL:\n" + response["sql"])
    for m in response.get("mappings") or []:
        print(f"  mapping: {m}")
    for a in response.get("assumptions") or []:
        print(f"  assumption: {a}")
    if response.get("explanation"):
        print("\nExplanation:\n" + response["explanation"]["text"])
    if response.get("answer"):
        print("\n" + response["answer"])
    results = response.get("results")
    if results:
        if results.get("error"):
            print(f"\nExecution error: {results['error']}")
        else:
            print(f"\nResults: {results['row_count']} of {results.get('total_rows')} rows — {results['columns']}")
            for row in results["rows"][:5]:
                print(f"  {row}")
    if response.get("cost"):
        c = response["cost"]
        print(f"\nCost: {c['level']} (score {c['score']}); index advice: "
              f"{[r['ddl'] for r in c.get('recommendations', [])]}")
    if response.get("clarification"):
        print(f"Options: {response['clarification']['options']}")
    d = response["dev"]
    print(f"\nPipeline: {' → '.join(e['node'] for e in d['trace'])}")
    for call in d["llm_calls"]:
        print(f"  LLM {call['step']:<22} {call['ms']:>6} ms  {call.get('served_by') or call['model']}"
              f"  ({call['route_reason']}){'  FAILED: ' + call['error'] if not call['ok'] else ''}")
    t = d["totals"]
    print(f"  totals: {t['llm_calls']} calls, {t['input_tokens']} in / {t['output_tokens']} out tokens, "
          f"cost ${t['cost_usd']}, pipeline {t['pipeline_ms']} ms")
    if dev:
        print(json.dumps({k: d[k] for k in ("intent", "plan", "grounded_plan", "validation_history")},
                         indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("questions", nargs="+")
    parser.add_argument("--thread", default=None, help="conversation id (follow-ups share a thread)")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    agent = SQLAgent()
    thread = args.thread or uuid.uuid4().hex
    for q in args.questions:
        print("=" * 100 + f"\nUSER: {q}")
        show(agent.run(q, thread_id=thread, options={"execute": not args.no_execute}), args.dev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
