"""Export controller — download the FULL result of an answer as CSV.

The chat shows at most MAX_RESULT_ROWS rows. The export re-runs the turn's SQL —
re-validated, through the same read-only connection — with a much higher cap
(EXPORT_MAX_ROWS) and streams it as CSV.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator

from fastapi import HTTPException

from controllers.context import AppServices


def export_csv(svc: AppServices, request_id: str, client: str) -> tuple[Iterator[str], str]:
    turn = svc.threads.get_turn(request_id)
    if not turn or turn["client_id"] != client:
        raise HTTPException(status_code=404, detail="Result not found.")
    sql = turn["response"].get("sql")
    if not sql or turn["response"].get("type") != "sql":
        raise HTTPException(status_code=400, detail="This answer has no query to export.")

    deps = svc.agent.deps
    report = deps.validator.validate(sql)
    if not report.ok:
        raise HTTPException(status_code=400, detail="The stored query no longer passes validation.")
    result = deps.db.execute(report.sql, max_rows=deps.settings.export_max_rows)

    def rows() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(result.columns)
        yield buffer.getvalue()
        for i in range(0, len(result.rows), 1000):
            buffer.seek(0)
            buffer.truncate()
            writer.writerows(result.rows[i:i + 1000])
            yield buffer.getvalue()

    slug = re.sub(r"[^a-z0-9]+", "-", turn["question"].lower()).strip("-")[:50] or "results"
    return rows(), f"{slug}.csv"
