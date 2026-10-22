"""Export the README and every document in docs/ to PDF (docs/pdf/<name>.pdf).

Markdown is rendered with Python-Markdown (tables, fenced code with Pygments highlighting, heading anchors),
mermaid diagrams are drawn by mermaid.js in headless Chromium, and Chromium prints the page to A4.
Links to other documents point to their PDF; links to source files point to the GitHub repository.

Requires the "docs" extra and a Chromium build for Playwright, plus internet access for mermaid.js:
    pip install -e ".[docs]"
    python -m playwright install chromium

Usage (from backend/):
    python scripts/export_docs_pdf.py                  # README.md + docs/*.md
    python scripts/export_docs_pdf.py docs/workflow.md # selected files (paths relative to the repo root)
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
OUT = DOCS / "pdf"
REPO_URL = "https://github.com/anunadhu1234/unifyapps-fd-assignment/blob/main"
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js"

MERMAID_FENCE = re.compile(r"^```mermaid\s*\n(.*?)^```\s*$", re.S | re.M)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
HREF = re.compile(r'(href|src)="([^"#:]+?)(#[^"]*)?"')

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
* { box-sizing: border-box; }
body { font: 10.5px/1.55 "Segoe UI", "Helvetica Neue", Arial, sans-serif; color: #1f2328; margin: 0; }
h1, h2, h3, h4 { color: #1e1b4b; line-height: 1.25; margin: 1.4em 0 .5em; break-after: avoid; }
h1 { font-size: 22px; border-bottom: 2px solid #4f46e5; padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 16px; border-bottom: 1px solid #e0e7ff; padding-bottom: 4px; }
h3 { font-size: 13px; }
h4 { font-size: 11.5px; }
p, ul, ol { margin: .45em 0 .7em; }
li { margin: .15em 0; }
a { color: #4338ca; text-decoration: none; }
hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1.2em 0; }
blockquote { margin: .8em 0; padding: .4em .9em; border-left: 3px solid #6366f1; background: #eef2ff; color: #3730a3; }
blockquote p { margin: .2em 0; }
code { font: 9.5px/1.45 "Cascadia Mono", Consolas, "Courier New", monospace; background: #f3f4f6;
       padding: .5px 4px; border-radius: 3px; font-variant-ligatures: none; }
pre, .codehilite { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 10px;
                   overflow: hidden; break-inside: avoid; margin: .6em 0 .9em; }
pre code { background: none; padding: 0; font-size: 8.3px; white-space: pre-wrap; word-break: break-word; }
.codehilite pre { border: 0; padding: 0; margin: 0; background: none; }
table { border-collapse: collapse; width: 100%; margin: .6em 0 1em; font-size: 9.5px; }
th, td { border: 1px solid #d0d7de; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #eef2ff; color: #1e1b4b; font-weight: 600; }
tr { break-inside: avoid; }
tbody tr:nth-child(even) td { background: #fafbff; }
td code { font-size: 8.8px; word-break: break-word; }
th code { font-size: 8.8px; white-space: nowrap; }
img { max-width: 100%; border: 1px solid #e5e7eb; border-radius: 6px; }
td img { max-height: 210px; }
.mermaid-slot { margin: .8em 0 1.1em; text-align: center; break-inside: avoid; }
.mermaid-slot svg { max-width: 100%; height: auto; max-height: 175mm; }
.doc-meta { color: #6b7280; font-size: 9px; margin-bottom: 14px; }
"""

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><base href="{base}"><title>{title}</title>
<style>{css}{pygments}</style></head>
<body><div class="doc-meta">{source}</div>{body}
<script src="{mermaid_js}"></script>
<script>
  window.__diagrams = {diagrams};
  (async () => {{
    try {{
      mermaid.initialize({{ startOnLoad: false, theme: "neutral", securityLevel: "loose",
                           flowchart: {{ htmlLabels: true }}, fontFamily: "Segoe UI, Arial, sans-serif" }});
      for (const [i, src] of window.__diagrams.entries()) {{
        const slot = document.querySelector(`.mermaid-slot[data-i="${{i}}"]`);
        const {{ svg }} = await mermaid.render(`diagram-${{i}}`, src);
        slot.innerHTML = svg;
      }}
      await Promise.all([...document.images].map(img => img.complete ? null :
        new Promise(r => {{ img.onload = img.onerror = r; }})));
      window.__ready = "ok";
    }} catch (e) {{ window.__ready = "error: " + e; }}
  }})();
</script></body></html>"""


def slugify(value: str, separator: str) -> str:
    """GitHub-style heading anchors, so the docs' tables of contents keep working."""
    value = re.sub(r"<[^>]+>", "", value).strip().lower()
    value = re.sub(r"[^\w\- ]", "", value)
    return value.replace(" ", separator)


def rewrite_links(body: str, source: Path) -> str:
    """Document links → sibling PDFs; source-code links → GitHub; images stay local (resolved via <base>)."""

    def fix(match: re.Match) -> str:
        attr, target, anchor = match.group(1), match.group(2), match.group(3) or ""
        if attr == "src":
            return match.group(0)
        resolved = (source.parent / target).resolve()
        if resolved.suffix == ".md":
            return f'href="{resolved.stem}.pdf{anchor}"'
        try:
            rel = resolved.relative_to(REPO).as_posix()
        except ValueError:
            return match.group(0)
        return f'href="{REPO_URL}/{rel}{anchor}"'

    return HREF.sub(fix, body)


def render(source: Path) -> tuple[str, int]:
    text = source.read_text(encoding="utf-8")
    diagrams: list[str] = []

    def stash(match: re.Match) -> str:
        diagrams.append(match.group(1).strip())
        return f'\n<div class="mermaid-slot" data-i="{len(diagrams) - 1}"></div>\n'

    text = MERMAID_FENCE.sub(stash, text)
    text = HTML_COMMENT.sub("", text)
    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "codehilite", "toc", "sane_lists", "attr_list"],
        extension_configs={"codehilite": {"guess_lang": False, "css_class": "codehilite"},
                           "toc": {"slugify": slugify}},
    )
    body = rewrite_links(md.convert(text), source)
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), source.stem)
    from pygments.formatters import HtmlFormatter

    page = PAGE.format(
        base=source.parent.resolve().as_uri() + "/",
        title=html.escape(title),
        css=CSS,
        pygments=HtmlFormatter(style="friendly").get_style_defs(".codehilite"),
        source=html.escape(f"{source.relative_to(REPO).as_posix()} · SQL Query AI Agent"),
        body=body,
        mermaid_js=MERMAID_JS,
        diagrams=json.dumps(diagrams),
    )
    return page, len(diagrams)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="markdown files relative to the repo root")
    args = parser.parse_args()
    sources = [REPO / f for f in args.files] or [REPO / "README.md", *sorted(DOCS.glob("*.md"))]
    OUT.mkdir(parents=True, exist_ok=True)

    footer = ('<div style="width:100%;font:8px Segoe UI,Arial;color:#9ca3af;padding:0 14mm;display:flex;'
              'justify-content:space-between"><span class="title"></span>'
              '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    failures = 0
    with sync_playwright() as pw, tempfile.TemporaryDirectory() as tmp:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for source in sources:
            html_text, n_diagrams = render(source)
            staged = Path(tmp) / f"{source.stem}.html"
            staged.write_text(html_text, encoding="utf-8")
            page.goto(staged.as_uri(), wait_until="networkidle")
            page.wait_for_function("window.__ready !== undefined", timeout=60_000)
            status = page.evaluate("window.__ready")
            target = OUT / f"{source.stem}.pdf"
            if status != "ok":
                failures += 1
                print(f"  [FAIL] {source.relative_to(REPO)}: {status}")
                continue
            page.pdf(path=str(target), format="A4", print_background=True, display_header_footer=True,
                     header_template="<span></span>", footer_template=footer,
                     margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"})
            print(f"  [ok]   {source.relative_to(REPO)} → {target.relative_to(REPO)} ({n_diagrams} diagrams)")
        browser.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
