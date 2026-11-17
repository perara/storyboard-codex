"""Build a static Storyboard from a validated story database."""

import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from urllib.parse import quote, urlsplit

from story_workflow import default_database, load_categories, load_db, load_diagrams


ASSETS = Path(__file__).resolve().parents[1] / "assets"
MAX_COLUMNS = 6
LOG_PREVIEW_CHARS = 16 * 1024
STATES = {"later": "Later", "planned": "Planned", "building": "Building", "works": "Works"}
REVIEWS = {"proposed": "Proposed", "agreed": "Agreed"}


def options(values):
    return "".join(f'<option value="{escape(key)}">{escape(label)}</option>' for key, label in values.items())


def chip(value, label):
    return f'<span class="chip" data-value="{escape(value)}">{escape(label)}</span>'


def visible_records(records, include_all):
    return [record for record in records if include_all or record.get("publish") is True]


def coverage(story):
    return len({check for record in story["proof"] for check in record["checks"]}), len(story["acceptance"])


def proof_label(story):
    covered, total = coverage(story)
    if not total:
        return "No checks"
    return f"{covered}/{total} checks covered" if covered else "No proof"


def catalog_entry(story, categories):
    identifier = escape(story["id"])
    state, review = story["state"], story["review"]
    covered, total = coverage(story)
    if not total:
        proof_state, proof_text = "no-checks", "No checks"
    elif not covered:
        proof_state, proof_text = "missing", "No proof"
    else:
        proof_state = "complete" if covered == total else "partial"
        proof_text = f"{covered}/{total} checks"
    return f"""
<li class="record-entry" data-id="{identifier}" data-category="{escape(story['category'])}"
    data-state="{state}" data-review="{review}" data-modules="{escape(' '.join(story['modules']))}">
  <a class="record-link" href="#{identifier}">
    <span class="record-line">
      <span class="record-id">{identifier}</span>
      <span class="record-category">{escape(categories[story['category']])}</span>
    </span>
    <span class="record-title">{escape(story['title'])}</span>
    <span class="record-bottom">
      <span class="record-delivery"><span class="sr-only">Delivery </span>{chip(state, STATES[state])}</span>
      <span class="record-review"><span class="sr-only">Review </span>{chip(review, REVIEWS[review])}</span>
      <span class="record-proof" data-coverage="{proof_state}"><span class="sr-only">Proof </span>{proof_text}</span>
    </span>
  </a>
</li>
"""


def overview_panel(story):
    facts = "".join(
        f"<div><dt>{field.title()}</dt><dd>{escape(story[field])}</dd></div>"
        for field in ("actor", "goal", "benefit")
    )
    details = f'<p class="record-description">{escape(story["details"])}</p>' if story["details"] else ""
    checks = "".join(
        f'<li><span class="check-id">{escape(check["id"])}</span><span class="check-copy">{escape(check["text"])}</span></li>'
        for check in story["acceptance"]
    )
    acceptance = f'<ol class="check-list">{checks}</ol>' if checks else '<p class="muted">No acceptance checks yet.</p>'
    return f"""
<h3 class="section-title">Story details</h3>
<dl class="story-facts">{facts}</dl>
{details}
<h3 class="section-title">Acceptance checks</h3>
{acceptance}
"""


def diagram_panel(story_id, diagram):
    return f"""
<figure id="diagram-{story_id}" class="behavior-diagram">
  <figcaption class="diagram-actions">
    <span>Behavior diagram</span>
    <button class="control-button enlarge-diagram" type="button" hidden>Enlarge diagram</button>
  </figcaption>
  <div class="diagram-view" aria-live="polite"></div>
  <details class="diagram-source">
    <summary>Mermaid source</summary>
    <pre>{escape(diagram)}</pre>
  </details>
</figure>
"""


def log_preview(path, checks):
    with path.open(encoding="utf-8") as stream:
        text = stream.read(LOG_PREVIEW_CHARS + 1)
    truncated = '<p class="muted">Preview shortened. Download the full log for more.</p>' if len(text) > LOG_PREVIEW_CHARS else ""
    return f'<pre class="log-preview" tabindex="0" aria-label="Log for {escape(checks)}">{escape(text[:LOG_PREVIEW_CHARS])}</pre>{truncated}'


def evidence_card(db, record):
    url = quote(record["path"])
    kind = record["kind"]
    title = "Run log" if kind == "log" else "Screenshot"
    checks = ", ".join(record["checks"])
    observation = escape(record["observation"])
    preview = log_preview(db / record["path"], checks) if kind == "log" else (
        f'<img class="attachment-preview" src="{url}" alt="{observation}" loading="lazy">'
    )
    return f"""
<li class="evidence-card">
  <div class="proof-actions">
    <h3 class="evidence-title">{title}</h3>
    <a class="control-button" href="{url}" download>Download {kind}</a>
  </div>
  <dl class="evidence-meta">
    <div><dt>Checks</dt><dd>{escape(checks)}</dd></div>
    <div><dt>Environment</dt><dd>{escape(record['environment'])}</dd></div>
    <div><dt>Build</dt><dd>{escape(record['revision'])}</dd></div>
    <div><dt>Observed</dt><dd>{escape(record['observed_on'])}</dd></div>
  </dl>
  <p>{observation}</p>
  {preview}
</li>
"""


def proof_panel(db, story, include_proof):
    covered, total = coverage(story)
    records = story["proof"]
    published = visible_records(records, include_proof)
    meter = f'<progress aria-label="Acceptance checks covered" value="{covered}" max="{total}"></progress>' if total else ""
    cards = "".join(evidence_card(db, record) for record in published)
    if not records:
        status = "No proof has been recorded."
    elif not published:
        status = "Evidence was recorded. Files are private."
    elif len(published) < len(records):
        status = "Some evidence files are private."
    else:
        status = ""
    note = f'<p class="muted">{status}</p>' if status else ""
    return f"""
<div class="proof-overview">
  <h3 class="section-title">Acceptance coverage</h3>
  <p class="proof-status">{covered} of {total} checks covered</p>
  {meter}
</div>
{note}
<ul class="evidence-list">{cards}</ul>
"""


def local_attachment(target):
    return not urlsplit(target).scheme


def attachments_panel(attachments):
    cards = []
    for record in attachments:
        label = escape(record["label"])
        target = record["target"]
        preview = ""
        if local_attachment(target):
            url = quote(target)
            extension = Path(target).suffix.lower()
            kind = "PDF" if extension == ".pdf" else extension.lstrip(".").upper()
            if extension in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                preview = f'<img class="attachment-preview" src="{url}" alt="" loading="lazy">'
            elif extension in {".mp4", ".webm"}:
                preview = f'<video class="attachment-preview" src="{url}" aria-label="{label}" controls playsinline preload="none"></video>'
            elif extension in {".mp3", ".ogg", ".wav"}:
                preview = f'<audio class="attachment-preview" src="{url}" aria-label="{label}" controls preload="none"></audio>'
        else:
            url = escape(target)
            kind = "Link"
        cards.append(f"""
<li class="attachment-card">
  <a href="{url}" target="_blank" rel="noopener noreferrer">
    <span class="attachment-type">{kind}</span>
    <span class="attachment-label">{label}</span>
  </a>
  {preview}
</li>
""")
    return f'<h3 class="section-title">Attachments</h3><ul class="attachment-grid">{"".join(cards)}</ul>'


def record_panel(db, story, modules, categories, include_proof, include_media, diagram):
    identifier = escape(story["id"])
    category = escape(categories[story["category"]])
    state, review = story["state"], story["review"]
    sections = [("overview", "Overview", overview_panel(story))]
    if diagram is not None:
        sections.append(("behavior", "Behavior", diagram_panel(identifier, diagram)))
    sections.append(("proof", "Proof", proof_panel(db, story, include_proof)))
    attachments = visible_records(story["attachments"], include_media)
    if attachments:
        sections.append(("files", "Files", attachments_panel(attachments)))
    tabs = []
    panels = []
    for key, label, content in sections:
        route = f"#{identifier}" if key == "overview" else f"#{identifier}/{key}"
        tabs.append(f'<a class="record-tab" id="tab-{identifier}-{key}" href="{route}" data-section="{key}">{label}</a>')
        panels.append(f'<section class="record-section" id="panel-{identifier}-{key}" data-section="{key}">{content}</section>')
    module_tags = "".join(f'<li class="module-tag">{escape(modules[module])}</li>' for module in story["modules"])
    module_list = f'<ul class="module-list" aria-label="Affected modules">{module_tags}</ul>' if module_tags else ""
    return f"""
<article class="record-panel" id="record-{identifier}" data-id="{identifier}" aria-labelledby="heading-{identifier}">
  <header class="record-header">
    <a class="mobile-back control-button" href="#catalog">All records</a>
    <p class="record-kicker"><span class="record-id">{identifier}</span><span>{category}</span></p>
    <h2 class="record-heading" id="heading-{identifier}" tabindex="-1">{escape(story['title'])}</h2>
    <div class="record-tags">{chip(state, STATES[state])}{chip(review, REVIEWS[review])}</div>
    {module_list}
  </header>
  <nav class="record-tabs" aria-label="Record sections">{"".join(tabs)}</nav>
  {"".join(panels)}
</article>
"""


def column_heading(module, label):
    return f'<th scope="col" class="module-column" data-module="{escape(module)}">{escape(label)}</th>'


def matrix_row(story, modules, categories, pinned):
    identifier = escape(story["id"])
    state, review = story["state"], story["review"]
    affected = ", ".join(escape(modules[module]) for module in story["modules"]) or "Not mapped"
    cells = "".join(
        f'<td class="module-column module-value">{"Affected" if module in story["modules"] else "—"}</td>'
        for module in pinned
    )
    return f"""
<tr data-id="{identifier}">
  <th scope="row"><a href="#{identifier}"><span class="record-id">{identifier}</span> {escape(story['title'])}</a></th>
  <td>{escape(categories[story['category']])}</td><td>{chip(review, REVIEWS[review])}</td>
  <td>{chip(state, STATES[state])}</td><td>{affected}</td><td><a href="#{identifier}/proof">{proof_label(story)}</a></td>{cells}
</tr>
"""


def render(db, modules, categories, stories, pinned, include_proof, include_media, diagrams):
    catalog = "".join(catalog_entry(story, categories) for story in stories)
    panels = "".join(record_panel(db, story, modules, categories, include_proof, include_media,
                                 diagrams.get(story["id"])) for story in stories)
    matrix = "".join(matrix_row(story, modules, categories, pinned) for story in stories)
    module_options = options(modules)
    state_counts = Counter(story["state"] for story in stories)
    status_buttons = "".join(
        f'<button class="state-button" type="button" value="{key}" aria-pressed="{str(not key).lower()}">'
        f'<span class="state-dot" data-value="{key}" aria-hidden="true"></span>'
        f'<span class="state-name">{label}</span><span class="state-count">{count}</span></button>'
        for key, label, count in [("", "All", len(stories)), *[(key, label, state_counts[key]) for key, label in STATES.items()]]
    )
    css = (ASSETS / "storyboard.css").read_text(encoding="utf-8")
    script = (ASSETS / "storyboard.js").read_text(encoding="utf-8")
    if diagrams:
        script += "\n" + (ASSETS / "storyboard-diagrams.js").read_text(encoding="utf-8")
    mermaid_asset = '<script defer src="assets/mermaid/mermaid.min.js"></script>' if diagrams else ""
    diagram_dialog = """
<dialog class="diagram-dialog" id="diagram-dialog" aria-labelledby="diagram-dialog-title">
  <div class="dialog-header">
    <h2 id="diagram-dialog-title">Behavior diagram</h2>
    <form method="dialog"><button type="submit" class="control-button" autofocus>Close diagram</button></form>
  </div>
  <div class="dialog-image" tabindex="0" aria-label="Full size behavior diagram"></div>
</dialog>
""" if diagrams else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Storyboard</title>
  <style>{css}</style>
  {mermaid_asset}
</head>
<body>
<a class="skip-link" href="#main-content">Skip to records</a>
<header class="masthead">
  <div class="masthead-inner">
    <a class="brand" href="#catalog" aria-label="Storyboard home">
      <span class="brand-mark" aria-hidden="true">S</span><span class="brand-name">Storyboard</span>
    </a>
    <nav class="view-switch" aria-label="Storyboard views">
      <a class="view-link" href="#catalog" aria-current="page">Browse records</a>
      <a class="view-link" href="#compare">Compare modules</a>
    </nav>
  </div>
</header>
<main class="app-shell" id="main-content">
  <section class="overview-bar" aria-label="Record summary">
    <div class="overview-heading">
      <h1>Records</h1>
      <p class="overview-meta">{len(stories)} records across {len(modules)} modules</p>
    </div>
    <div class="state-picker" role="group" aria-label="Filter by delivery state">{status_buttons}</div>
  </section>

  <div class="workbench">
    <section class="catalog-pane" id="catalog-pane" aria-label="Record catalog">
      <div class="catalog-toolbar">
        <label class="search-label">Search records<input id="search" type="search" placeholder="Title, ID, or keyword" autocomplete="off"></label>
        <details class="filter-menu">
          <summary>Filters <span class="filter-count" hidden></span></summary>
          <div class="filter-grid">
            <label><span id="category-label">Category</span><select id="category" aria-labelledby="category-label"><option value="">Any category</option>{options(categories)}</select></label>
            <label><span id="state-label">Delivery</span><select id="state" aria-labelledby="state-label"><option value="">Any state</option>{options(STATES)}</select></label>
            <label><span id="review-label">Review</span><select id="review" aria-labelledby="review-label"><option value="">Any review</option>{options(REVIEWS)}</select></label>
            <label><span id="module-label">Affected module</span><select id="module" aria-labelledby="module-label"><option value="">Any module</option>{module_options}</select></label>
          </div>
        </details>
        <div class="catalog-tools">
          <span class="result-count" role="status">{len(stories)} records</span>
          <button class="clear-filters" type="button" hidden>Clear filters</button>
        </div>
      </div>
      <ul class="record-list" aria-label="Records">{catalog}</ul>
      <div class="empty-state" id="catalog-empty" {"hidden" if stories else ""}>
        <p>{"No records match your filters." if stories else "No records yet."}</p>
      </div>
    </section>
    <section class="reader" id="record-reader" aria-label="Record details">{panels}</section>
  </div>

  <section class="matrix" id="compare" aria-labelledby="matrix-title" hidden>
    <header class="matrix-header">
      <h2 id="matrix-title">Compare modules</h2>
      <div class="column-toolbar">
        <label><span id="column-label">Module column</span><select id="columns" aria-labelledby="column-label" data-max="{MAX_COLUMNS}" data-defaults="{escape(json.dumps(pinned))}">
          <option value="">Choose a module</option>{module_options}
        </select></label>
        <button class="control-button" id="pin" type="button" disabled>Add column</button>
      </div>
    </header>
    <div class="board" role="region" aria-label="Module comparison" tabindex="0">
      <table aria-label="Module comparison">
        <thead><tr>
          <th scope="col">Record</th><th scope="col">Category</th><th scope="col">Review</th><th scope="col">Delivery</th>
          <th scope="col">Affected modules</th><th scope="col">Proof</th>
          {"".join(column_heading(module, modules[module]) for module in pinned)}
        </tr></thead>
        <tbody>{matrix}</tbody>
      </table>
    </div>
    <p class="empty-state" id="matrix-empty" hidden>No records to compare.</p>
  </section>
</main>
{diagram_dialog}
<script>{script}</script>
</body>
</html>
"""


def export(db, out, selected_modules, include_proof, include_media=False):
    db, out = db.resolve(), out.resolve()
    if out.is_relative_to(db) or db.is_relative_to(out):
        raise ValueError("Export directory must be separate from the database")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("Export destination must be a new or empty directory")
    modules, stories = load_db(db)
    diagrams = load_diagrams(db, stories)
    categories = load_categories(db)
    pinned = list(dict.fromkeys(selected_modules))
    if len(pinned) > MAX_COLUMNS or any(module not in modules for module in pinned):
        raise ValueError(f"Select up to {MAX_COLUMNS} known module IDs")

    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".story-export-", dir=out.parent) as temporary:
        site = Path(temporary) / "site"
        site.mkdir()
        (site / "index.html").write_text(
            render(db, modules, categories, stories, pinned, include_proof, include_media, diagrams), encoding="utf-8"
        )
        (site / ".nojekyll").touch()
        if diagrams:
            assets = site / "assets" / "mermaid"
            assets.mkdir(parents=True)
            for filename in ("mermaid.min.js", "LICENSE"):
                copyfile(ASSETS / "mermaid" / filename, assets / filename)
        paths = set()
        for story in stories:
            paths.update(record["path"] for record in visible_records(story["proof"], include_proof))
            paths.update(
                record["target"] for record in visible_records(story["attachments"], include_media)
                if local_attachment(record["target"])
            )
        for path in sorted(paths):
            target = site / path
            target.parent.mkdir(parents=True, exist_ok=True)
            copyfile(db / path, target)
        if out.exists():
            out.rmdir()
        site.rename(out)
    return len(stories)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="database directory (default: stories in the Git repo)")
    parser.add_argument("--out", type=Path, required=True, help="new or empty site directory")
    parser.add_argument("--module", action="append", default=[], help="pin a module column by ID (repeatable)")
    parser.add_argument("--include-proof", action="store_true", help="include all proof, including items without publish=true")
    parser.add_argument("--include-media", action="store_true", help="include all attachments, including items without publish=true")
    args = parser.parse_args()
    try:
        count = export(args.db or default_database(), args.out, args.module, args.include_proof, args.include_media)
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Exported {count} records to {args.out / 'index.html'}")


if __name__ == "__main__":
    main()
