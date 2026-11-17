---
name: story-workflow
description: Bootstrap, maintain, and host a Git-backed Storyboard for user stories and other work items. Use for a local dashboard, GitHub Pages, intake, categories, affected modules, behavior diagrams, multimedia attachments, and acceptance proof.
---

# Storyboard

## 1. Identify the input

Locate the target Git repository or worktree and inspect its status before writing. For setup, run the bundled script as `python3 /path/to/skill/scripts/story_workflow.py bootstrap`. It creates or reuses `stories/`, copies the standalone tools to `tools/storyboard/`, and builds `_storyboard/index.html`. Add `--pages` when the user asks for GitHub Pages. When a repository stores records elsewhere, pass `--db PATH` before the command.

Use `python3 -B tools/storyboard/scripts/story_workflow.py preview` from the repository root to rebuild the dashboard after editing. Give the user the preview path. If they want a local server, pass `--serve` and share the printed localhost URL. Use `--include-proof` or `--include-media` when the local view should include unpublished files.

Identify what arrived before editing. A **user story** describes a specific actor, goal, and benefit. A **bug** describes a gap between current and expected behavior. **Technical** work targets an engineering outcome. **Research** starts with a question and the result needed for a decision. Use the repository's categories when it defines them. For a user story, check that the input describes one independently useful, observable outcome. Split an epic into smaller user outcomes and link implementation tasks to the outcome they support.

Search first with `story_workflow.py --db stories find "invoice download"`. Use `--category ID` to narrow the search when helpful and try the actor, goal, or keywords in different combinations. Say whether the input appears new or matches an existing ID, which category fits, and why. Update a clear match within the user's scope. Present likely duplicates for review and keep their IDs intact while the match remains uncertain.

## 2. Record the outcome

```sh
python3 /path/to/skill/scripts/story_workflow.py --db stories new --title 'Download an invoice' --actor 'Account holder' --goal 'Download a paid invoice as a PDF' --benefit 'Keep a copy for expense records' --category user-story
python3 /path/to/skill/scripts/story_workflow.py --db stories attach RECORD_ID invoice-example.pdf --label 'Example invoice'
```

Use the ID printed in the filename by `new` in later commands. Start with `review: proposed` and state `planned` or `later`. Use `--details TEXT` or edit the JSON to add context that helps the reader understand the behavior. For other categories, use the most relevant actor or stakeholder and state the outcome and reason. Use a few observable acceptance checks. Reuse IDs from `modules.json` for directly affected components. Leave the list empty for work without an affected module.

When a diagram clarifies the behavior, write raw Mermaid to `diagrams/<record-id>.mmd` in the database. Use a flowchart for user choices and branches or a sequence diagram for handoffs. Match the agreed behavior and acceptance checks, include meaningful failure or retry paths, and add an accessible `accTitle` and `accDescr`. The expanded record renders it and includes its source. Diagram files use plain Mermaid without Markdown fences, front matter, or configuration directives.

Use `attach US-ID FILE_OR_HTTPS_URL [--label LABEL]` for supporting material such as PDFs, images, or links. The CLI copies local files under `media/<story-id>/`. Attachments stay out of the Pages export by default. Tracked files are visible to repository readers. Use `--publish` only for an attachment approved for the intended site audience.

## 3. Review, deliver, and verify

Mark the record `agreed` after the decision owner agrees to the behavior. Move it to `building` when delivery starts and acceptance checks are defined. Consult the team's work-in-progress limit before starting more stories. Surface items waiting on decisions or proof during review.

Record an observed passing result or relevant evidence the user supplied. Use a focused, redacted log for behavior or a screenshot for a visible result. A single artifact can cover multiple checks it demonstrates. Put proof under `evidence/<story-id>/` and record the check IDs, revision or build identifier, environment, date, and observation. Mark it `works` once it is agreed and all checks have passing proof. If the behavior or a check changes materially, reopen the record and rerun the affected checks before restoring `works`.

## 4. Save the record in Git

Run `story_workflow.py check` for the selected database. Use `git status --short -- <database>` and review the touched paths, including untracked files. The record JSON, its referenced diagram, media and evidence, and any changed module or category definitions belong in the same change. Keep record IDs across title changes. If only the record changes, the JSON is the only file to save.

When asked to save a Git commit, stage the specific source paths and review the staged diff for those paths. Commit only those paths so unrelated staged work stays staged. Use the repository's existing branch and review conventions. Keep generated HTML and full JSONL exports outside the change. After committing, report the record ID and commit SHA and show any relevant files still untracked.

For GitHub Pages, review the export and the target site's audience before enabling it. Repositories with an existing site need to integrate the Storyboard export into that site's publishing workflow. For a new site, set **Settings → Pages → Source → GitHub Actions**, then land the bootstrap files through the normal Git review flow. The generated workflow builds on pull requests and publishes after changes reach the default branch. If Pages was enabled after the workflow landed, manually run **Storyboard** once from Actions. When asked to publish, verify the run and open the site URL before reporting it live.

## Files and fields

- `modules.json` maps lowercase kebab-case module IDs to display names.
- Optional `categories.json` maps category IDs to display names and must include `user-story`. The default IDs are `user-story`, `bug`, `technical`, and `research`.
- `items/<story-id>.json` holds `id`, `title`, `actor`, `goal`, `benefit`, `review` (`proposed` or `agreed`), `state` (`later`, `planned`, `building`, or `works`), `modules`, `acceptance` (entries with `id` such as `A1` and `text`), and `proof`. Optional fields are `category` (defaults to `user-story`), `details`, and `attachments`.
- Attachments have `label`, `target` (a relative path under `media/<story-id>/` or an HTTPS URL), and `publish`.
- Proof entries have `checks`, `kind` (`log` or `image`), `path` relative to the database, `revision`, `environment`, `observed_on` (`YYYY-MM-DD`), and `observation`. Use `.txt` or `.log` for logs and `.png`, `.jpg`, `.jpeg`, or `.webp` for images. Set the optional `publish` flag only for proof approved for the site audience.

## Export

```sh
python3 /path/to/skill/scripts/export_pages.py --db stories --out _site
python3 /path/to/skill/scripts/story_workflow.py --db stories jsonl
```

Repeat `--module ID` to choose the initial module columns. The Pages export includes story text, categories, and proof coverage. Individual attachments and proof files appear when marked `publish: true`. `jsonl` writes complete records to stdout for local tools.
