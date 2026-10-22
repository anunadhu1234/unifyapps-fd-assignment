"""Everything the nodes need, built once per process and passed to every node.

Nodes receive `deps` explicitly instead of importing globals, which keeps them
pure functions of (state, deps) and lets tests inject a scripted LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from agent.exec.cost_estimator import CostEstimator
from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.guardrails.sql_validator import SQLValidator
from agent.knowledge.kb_resolver import KnowledgeBase, get_kb
from agent.llm_client import BedrockGateway, LLMGateway, LoggingGateway, ModelRouter
from utils.config import Settings, get_settings


@dataclass
class AgentDeps:
    settings: Settings
    kb: KnowledgeBase
    db: ReadOnlyDatabase
    llm: LLMGateway
    validator: SQLValidator
    cost: CostEstimator
    examples: list[dict]


def load_examples(knowledge_dir: Path) -> list[dict]:
    path = knowledge_dir / "examples.yaml"
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("examples", [])


def build_deps(settings: Settings | None = None, llm: LLMGateway | None = None) -> AgentDeps:
    settings = settings or get_settings()
    kb = get_kb()
    db = ReadOnlyDatabase(settings.database_path, timeout_s=settings.query_timeout_s,
                          max_rows=settings.max_result_rows)
    return AgentDeps(
        settings=settings,
        kb=kb,
        db=db,
        # Every gateway (real or test double) is wrapped so the dev console sees each LLM stage.
        llm=LoggingGateway(llm or BedrockGateway(settings), ModelRouter(settings)),
        validator=SQLValidator(kb, db),
        cost=CostEstimator(kb, db),
        examples=load_examples(settings.knowledge_dir),
    )
