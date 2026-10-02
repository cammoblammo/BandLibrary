"""
Text and HTML rendering for the consistency report.
"""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime

from .report import EnsembleReport, Finding, Report
from .utils import display_title

REASONS = ("direct", "all", "fallback", "compromise", "assignment", "missing")
REASON_LABELS = {
    "direct": "Direct",
    "all": "All parts",
    "fallback": "Fallback",
    "compromise": "Compromise",
    "assignment": "Assigned",
    "missing": "Missing",
}


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------

def render_text(report: Report) -> str:
    lines: list[str] = []

    def print(text: str = "") -> None:  # collect lines instead of printing
        lines.append(text)

    print(f"Library: {len(report.pieces)} piece(s)")
    for err in report.load_errors:
        print(f"  ERROR loading {err}")
    print()

    for e in report.ensembles:
        total = sum(e.counts.values())
        summary = ", ".join(
            f"{REASON_LABELS[k]} {e.counts.get(k, 0)}"
            for k in REASONS
        )
        print(f"{e.name} ({e.key}): {len(e.parts)} chairs × {len(report.pieces)} pieces "
              f"= {total} — {summary}")
    print()

    grouped = _group_findings(report.findings)
    for (severity, category), items in grouped:
        print(f"{severity.upper()}: {category} ({len(items)})")
        for f in items:
            prefix = f"[{f.ensemble}] " if f.ensemble else ""
            print(f"  {prefix}{f.message}")
        print()

    return "\n".join(lines)


def _group_findings(findings: list[Finding]):
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in findings:
        groups[(f.severity, f.category)].append(f)
    order = {"warning": 0, "info": 1}
    return sorted(groups.items(), key=lambda kv: (order[kv[0][0]], kv[0][1]))


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

CSS = """
/* Layout: a single reading column for the summary and findings, with each
   ensemble's chair-by-piece grid in its own horizontally scrolling panel. */
:root {
  --paper: #f6f7f9;
  --ink: #1b2330;
  --muted: #5d6878;
  --rule: #d5dae2;
  --panel: #ffffff;
  --accent: #2c4f8f;
  --fallback-bg: #fbecc9;
  --fallback-fg: #6b4a05;
  --compromise-bg: #f6dcc4;
  --compromise-fg: #7a3a06;
  --assigned-bg: #dfe7f7;
  --assigned-fg: #23407a;
  --missing-bg: #f8d9d6;
  --missing-fg: #8a1f16;
  --warn: #a8560a;
  --info: #4a5a72;
  --font-display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --font-body: "Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #12161d; --ink: #e3e8ef; --muted: #98a3b3; --rule: #2c3442;
    --panel: #181e27; --accent: #8fb0ea;
    --fallback-bg: #3d3115; --fallback-fg: #f2d38a;
    --compromise-bg: #4a2a12; --compromise-fg: #f5bf8e;
    --assigned-bg: #1f2d48; --assigned-fg: #b3c8f0;
    --missing-bg: #4a1f1c; --missing-fg: #f4b4ad;
    --warn: #e8a35c; --info: #a7b4c8;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #12161d; --ink: #e3e8ef; --muted: #98a3b3; --rule: #2c3442;
  --panel: #181e27; --accent: #8fb0ea;
  --fallback-bg: #3d3115; --fallback-fg: #f2d38a;
  --compromise-bg: #4a2a12; --compromise-fg: #f5bf8e;
  --assigned-bg: #1f2d48; --assigned-fg: #b3c8f0;
  --missing-bg: #4a1f1c; --missing-fg: #f4b4ad;
  --warn: #e8a35c; --info: #a7b4c8;
  color-scheme: dark;
}
body {
  background: var(--paper); color: var(--ink);
  font-family: var(--font-body); font-size: 15px; line-height: 1.55;
  margin: 0; padding: 0 16px;
}
.wrap { max-width: 1100px; margin: 0 auto; padding-block: 32px 64px; }
.staff { display: grid; gap: 5px; margin-bottom: 20px; max-width: 220px; }
.staff span { display: block; height: 1px; background: var(--rule); }
h1, h2, h3 { font-family: var(--font-display); text-wrap: balance; line-height: 1.2; margin: 0; }
h1 { font-size: 2rem; font-weight: 700; letter-spacing: -0.01em; }
h2 { font-size: 1.35rem; font-weight: 650; margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule); }
h3 { font-size: 1.05rem; font-weight: 650; margin-top: 28px; }
.lede { color: var(--muted); max-width: 65ch; margin: 8px 0 0; }
.eyebrow { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
code, .id { font-family: var(--font-mono); font-size: 0.85em; }

.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 24px; }
.ens { background: var(--panel); border: 1px solid var(--rule); border-radius: 6px; padding: 16px; min-width: 0; }
.ens h3 { margin: 0 0 2px; }
.ens .band { color: var(--muted); font-size: 0.85rem; }
.bar { display: flex; height: 10px; border-radius: 3px; overflow: hidden; margin: 14px 0 10px; background: var(--rule); }
.bar span { display: block; height: 100%; }
.legend { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 16px; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.legend div { display: flex; justify-content: space-between; gap: 8px; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.c-direct { background: var(--rule); }
.c-all { background: var(--muted); }
.c-fallback { background: var(--fallback-fg); }
.c-compromise { background: var(--compromise-fg); }
.c-assignment { background: var(--accent); }
.c-missing { background: var(--missing-fg); }

.findings { margin-top: 8px; display: grid; gap: 12px; }
details.group { background: var(--panel); border: 1px solid var(--rule); border-radius: 6px; min-width: 0; }
details.group summary {
  cursor: pointer; padding: 12px 16px; display: flex; gap: 10px; align-items: baseline;
  list-style: none; font-weight: 650;
}
details.group summary::-webkit-details-marker { display: none; }
details.group summary::before { content: "▸"; color: var(--muted); font-size: 0.8em; }
details.group[open] summary::before { content: "▾"; }
details.group summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.sev { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; padding: 2px 7px; border-radius: 3px; border: 1px solid currentColor; }
.sev-warning { color: var(--warn); }
.sev-info { color: var(--info); }
.count { margin-left: auto; color: var(--muted); font-variant-numeric: tabular-nums; font-weight: 400; }
details.group ul { margin: 0; padding: 0 16px 14px 36px; display: grid; gap: 6px; }
details.group li { max-width: 80ch; overflow-wrap: anywhere; }
.tag { font-size: 0.75rem; color: var(--muted); font-family: var(--font-mono); margin-right: 6px; }

.gridnote { color: var(--muted); max-width: 65ch; margin: 8px 0 12px; }
.scroller { overflow-x: auto; border: 1px solid var(--rule); border-radius: 6px; background: var(--panel); }
table.grid { border-collapse: separate; border-spacing: 0; font-size: 0.78rem; }
table.grid th, table.grid td { padding: 6px 8px; border-bottom: 1px solid var(--rule); white-space: nowrap; text-align: left; }
table.grid thead th { position: sticky; top: 0; background: var(--panel); font-weight: 650; vertical-align: bottom; z-index: 1; }
table.grid thead th.piece { font-size: 0.75rem; white-space: normal; min-width: 92px; max-width: 120px; line-height: 1.25; }
table.grid tbody th { position: sticky; left: 0; background: var(--panel); font-weight: 650; z-index: 2; border-right: 1px solid var(--rule); }
table.grid thead th.corner { left: 0; z-index: 3; position: sticky; border-right: 1px solid var(--rule); }
table.grid tbody th .fb { display: block; font-weight: 400; color: var(--muted); font-family: var(--font-mono); font-size: 0.7rem; white-space: normal; max-width: 220px; }
td.cell { font-family: var(--font-mono); }
td.direct { color: var(--muted); text-align: center; }
td.all { color: var(--muted); }
td.fallback { background: var(--fallback-bg); color: var(--fallback-fg); }
td.compromise { background: var(--compromise-bg); color: var(--compromise-fg); font-style: italic; }
td.assignment { background: var(--assigned-bg); color: var(--assigned-fg); }
td.missing { background: var(--missing-bg); color: var(--missing-fg); text-align: center; font-weight: 700; }
.foot { margin-top: 48px; color: var(--muted); font-size: 0.85rem; }
"""


def _e(text: str) -> str:
    return html.escape(str(text))


def render_html(report: Report, standalone: bool = True) -> str:
    parts: list[str] = []
    parts.append("<title>Fallback Consistency Report</title>")
    parts.append(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:wght@600;700'
        '&family=JetBrains+Mono:wght@400;600&display=swap">'
    )
    parts.append(f"<style>{CSS}</style>")
    parts.append('<div class="wrap">')
    parts.append('<div class="staff" aria-hidden="true">' + "<span></span>" * 5 + "</div>")
    parts.append('<div class="eyebrow">BandBook</div>')
    parts.append("<h1>Fallback consistency report</h1>")
    parts.append(
        f'<p class="lede">How every chair in each ensemble gets its music across all '
        f'{len(report.pieces)} pieces in the library, and where the fallback rules, '
        f'part names and assignments don\'t line up.</p>'
    )
    if report.load_errors:
        parts.append("<ul>" + "".join(
            f"<li>Could not load {_e(err)}</li>" for err in report.load_errors) + "</ul>")

    # Summary per ensemble
    parts.append('<div class="summary">')
    for e in report.ensembles:
        total = sum(e.counts.values()) or 1
        bar = "".join(
            f'<span class="c-{k}" style="width:{100 * e.counts.get(k, 0) / total:.2f}%"></span>'
            for k in REASONS
        )
        legend = "".join(
            f'<div><span><span class="sw c-{k}"></span>{REASON_LABELS[k]}</span>'
            f'<span>{e.counts.get(k, 0)}</span></div>'
            for k in REASONS
        )
        parts.append(
            f'<section class="ens"><h3>{_e(e.name)}</h3>'
            f'<div class="band">{_e(e.band)} · {len(e.parts)} chairs · '
            f'<span class="id">{_e(e.key)}.yaml</span></div>'
            f'<div class="bar" role="img" aria-label="Match breakdown">{bar}</div>'
            f'<div class="legend">{legend}</div></section>'
        )
    parts.append("</div>")

    # Findings
    parts.append("<h2>Findings</h2>")
    parts.append('<div class="findings">')
    for (severity, category), items in _group_findings(report.findings):
        is_open = " open" if severity == "warning" else ""
        lis = "".join(
            f'<li>{("<span class=tag>" + _e(f.ensemble) + "</span>") if f.ensemble else ""}'
            f"{_e(f.message)}</li>"
            for f in items
        )
        parts.append(
            f'<details class="group"{is_open}><summary>'
            f'<span class="sev sev-{severity}">{_e(severity)}</span>'
            f"<span>{_e(category)}</span><span class=\"count\">{len(items)}</span>"
            f"</summary><ul>{lis}</ul></details>"
        )
    parts.append("</div>")

    # Grids
    for e in report.ensembles:
        parts.append(f"<h2>{_e(e.name)}: who reads what</h2>")
        parts.append(
            '<p class="gridnote">Each row is a chair, each column a piece. '
            "A dot means the piece has that chair's own part. Shaded cells show "
            "the part the chair reads instead: amber from a preferred fallback "
            "(→), orange italic from a compromise (≈), blue from an assignment, "
            "red where the chair gets nothing.</p>"
        )
        parts.append(_render_grid(e, report))

    parts.append(
        f'<p class="foot">Generated by <code>tools/consistency_report.py</code> on '
        f'{datetime.now().strftime("%-d %B %Y, %H:%M")}.</p>'
    )
    parts.append("</div>")

    body = "\n".join(parts)
    if not standalone:
        return body + "\n"
    head, _, rest = body.partition("<div class=\"wrap\">")
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{head}\n</head>\n<body>\n<div class=\"wrap\">{rest}\n</body>\n</html>\n"
    )


def _render_grid(e: EnsembleReport, report: Report) -> str:
    rows: list[str] = []
    heads = "".join(
        f'<th class="piece" scope="col">{_e(display_title(p.title))}</th>'
        for p in report.pieces
    )
    rows.append(f'<thead><tr><th class="corner" scope="col">Chair</th>{heads}</tr></thead>')
    rows.append("<tbody>")
    for ep in e.parts:
        fb = ""
        if ep.reads:
            fb += f'<span class="fb">reads {_e(", ".join(ep.reads))}</span>'
        if ep.prefer_spec:
            fb += f'<span class="fb">→ {_e(", ".join(ep.prefer_spec))}</span>'
        if ep.compromise_spec:
            fb += f'<span class="fb">≈ {_e(", ".join(ep.compromise_spec))}</span>'
        if ep.takes_all:
            fb += '<span class="fb">takes every part it reads</span>'

        cells = []
        for p in report.pieces:
            r = e.grid[ep.id][p.slug]
            reason = r.match_reason or "missing"
            if reason == "direct":
                text = "·"
            elif reason == "missing":
                text = "—"
            else:
                text = _e(", ".join(r.matched_ids))
            label = f"{ep.label} in {p.title}: {REASON_LABELS[reason]}"
            if reason in ("fallback", "compromise", "assignment", "all"):
                label += f" ({', '.join(r.matched_ids)})"
            cells.append(f'<td class="cell {reason}" title="{_e(label)}">{text}</td>')
        rows.append(f'<tr><th scope="row">{_e(ep.label)}{fb}</th>{"".join(cells)}</tr>')
    rows.append("</tbody>")
    return f'<div class="scroller"><table class="grid">{"".join(rows)}</table></div>'


