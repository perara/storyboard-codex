# Storyboard usage

Install the Codex plugin from the [repository README](../README.md), or use Python and Git directly.

## Bootstrap a dashboard

Ask Codex to **set up Storyboard in this repository** or **set up Storyboard for GitHub Pages**. The Python 3.9+ bootstrap works from the command line too. Run it inside the target Git checkout:

```sh
python3 -B /path/to/storyboard-codex/plugins/story-workflow/skills/story-workflow/scripts/story_workflow.py bootstrap
```

Add `--pages` to prepare automatic GitHub Pages deployment. Bootstrap creates or reuses `stories/`, installs the standalone tools under `tools/storyboard/`, and builds `_storyboard/index.html`. You can rerun it. If an installed file differs from the package, bootstrap reports the conflict so you can review it. Use `--db PATH` before the command to choose a custom database within the checkout.

Open the printed dashboard path in your browser. From the Git root, rebuild it after changing a record with:

```sh
python3 -B tools/storyboard/scripts/story_workflow.py preview
# Or start a local server and open the URL it prints.
python3 -B tools/storyboard/scripts/story_workflow.py preview --serve
```

The checkout ignores `_storyboard/` in Git. Use `preview --include-proof --include-media` for a local view that includes unpublished files.

## See the sample records

```sh
# Run from the storyboard-codex checkout.
python3 -B plugins/story-workflow/skills/story-workflow/scripts/export_pages.py \
  --db plugins/story-workflow/examples/stories --out _story_demo \
  --module billing --module account-portal
```

Open `_story_demo/index.html`. Use a fresh or empty output directory for each export.

Each sidebar item shows delivery, review, and proof coverage in a consistent order. Select **Download an invoice** and open **Behavior** to view the diagram. Use **Enlarge diagram** for the full-size view. **Proof** shows acceptance coverage and the run log. **Files** holds the sample PDF, mockup, and reference link. Open **Compare modules** when you want the full table.

Ask Codex to draw a diagram for a record, or save raw Mermaid source in `stories/diagrams/<record-id>.mmd`. A flowchart works well for decisions and retries. A sequence diagram works well for interactions between systems. Keep the diagram to the behavior a reader needs to review and include `accTitle` and `accDescr` for an accessible summary. Mermaid source remains available in **Behavior**. [Mermaid accessibility syntax](https://mermaid.js.org/config/accessibility.html)

The exporter ships the bundled Mermaid 11.17.2 renderer with the page when diagrams are present. The page can render them offline. Diagram source is part of the story content included in Pages, and it uses regular Mermaid syntax without front matter or configuration directives. The renderer's MIT license is bundled alongside it.

Give Codex a file path or paste an HTTPS link and tell it which record to attach it to. The CLI copies a local file into the record's media folder and adds it to the expanded view.

```sh
python3 tools/storyboard/scripts/story_workflow.py find "invoice download"
python3 tools/storyboard/scripts/story_workflow.py attach US-001 ./invoice-mockup.pdf
python3 tools/storyboard/scripts/story_workflow.py attach US-001 https://example.org/design --label "Design notes"
```

Images, supported audio, and supported video have inline previews. PDFs open in the browser. Use an HTTPS link for a large file or a document already hosted elsewhere. Local attachments are limited to 20 MiB each.

## How the workflow stays small

| Need | Default |
| --- | --- |
| Identify work | Search for the same actor, outcome, or bug symptom. If needed, choose a category and create one record for the independently verifiable work. |
| Track work | One JSON file per record under `stories/items/`. Keep the ID when the title changes. Add a `categories.json` ID-to-label map to customize the four built-in categories. Existing records without a category are read as User story. |
| See impact | One module catalog (`stories/modules.json`) with stable IDs. Record modules directly touched by the story. Show them in a compact column and pin up to six comparison columns in the view. |
| Route decisions | Review is **Proposed** or **Agreed**. Delivery is **Later**, **Planned**, **Building**, or **Works**. An agreed story can still be planned. |
| Start work | **Building** requires agreement and observable acceptance checks. Affected modules can be empty for work that has no module. |
| Verify | **Works** requires passing proof for every acceptance check. One focused log or image can cover several checks. Each proof identifies what happened, where, when, and on which build or revision. |

Proof is a small file under `stories/evidence/<story-id>/` with a recorded observation. The expanded proof view shows the acceptance check IDs, revision, environment, date, and an inline screenshot or log excerpt with the original available for download. The validator checks file presence, type, and acceptance coverage. The reviewer checks that the evidence supports the claim. Reopen a story if a material change invalidates its proof.

## Save a story in Git

Create or update a record on the branch where you want it reviewed. The `new` command prints the record's path, for example `stories/items/US-r0123456789abcdef.json`. New IDs are generated independently on each branch. Earlier IDs such as `US-001` and their links remain valid.

Run `story_workflow.py check`, then use your usual Git workflow. For a JSON-only change:

```sh
git status --short -- stories
git add -- stories/items/US-r0123456789abcdef.json
git diff --cached --check -- stories/items/US-r0123456789abcdef.json
git commit --only -m "Add invoice download story" -- stories/items/US-r0123456789abcdef.json
```

Replace the example path with the actual record. Include any new or changed diagram, referenced media and evidence, and changed catalog files in the same commit. A new database also needs `stories/modules.json`. Commit source files, and use a temporary directory or local Git ignore for generated HTML and full JSONL exports. The normal Git merge rules apply when branches edit the same story or catalog entry.

Update the Codex plugin and the vendored Pages exporter together so both understand newly generated IDs.

## Build with GitHub Actions

Run `bootstrap --pages` to add `.github/workflows/storyboard-pages.yml`. Review and commit `stories/`, `tools/storyboard/`, the ignore rules, and the workflow using your normal Git review process. For a new Pages site, select **GitHub Actions** under **Settings → Pages → Source**. If the repo already has a Pages site, integrate the generated dashboard into its existing publishing workflow. [GitHub Pages setup](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

Pull requests validate the catalog. Pushes to the default branch publish it automatically after Pages is enabled. If setup is already on the default branch when you enable Pages, open **Actions → Storyboard → Run workflow** once. Find the published URL in the deploy job or in **Settings → Pages**. [GitHub Actions deployment](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)

The default Pages export displays story text, module names, and proof counts. It includes an attachment or proof file only when that entry has `"publish": true`. Use `attach --publish` for media approved for the Pages audience. Use `--include-media --include-proof` to inspect all records and files in a local or authorized private view. [GitHub Pages visibility](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/changing-the-visibility-of-your-github-pages-site)

## Record format and interoperability

Use one formatted JSON record per Git file so a pull request can review one record by itself. The [Storyboard JSON Schema](../plugins/story-workflow/schemas/storyboard.schema.json) describes the record shape using JSON Schema 2020-12. The CLI additionally verifies catalog references, story and check IDs, local files, and evidence coverage. [JSON Schema 2020-12](https://json-schema.org/draft/2020-12)

Use `story_workflow.py jsonl > storyboard.jsonl` for a local export to analysis tools or another importer. Each UTF-8 line contains one record, including its attachment and proof references. Copy the referenced files separately when transferring evidence. Treat this export as internal because it includes private references. JSON Lines defines record framing. The Storyboard schema defines the meaning of the fields. [JSON Lines](https://jsonlines.org/)

ReqIF 1.2 is an XML exchange standard for requirements tools. OSLC RM defines services and a vocabulary for connecting requirements systems. W3C PROV models provenance across systems. Use a mapping to one of these when an integration calls for it. Storyboard's proof fields already identify the artifact, the observed result, and the build and environment needed to review it. [OMG ReqIF](https://www.omg.org/spec/ReqIF) · [OASIS OSLC RM](https://docs.oasis-open-projects.org/oslc-op/rm/v2.1/os/requirements-management-spec.html) · [W3C PROV-O](https://www.w3.org/TR/prov-o/)

## Sources behind the defaults

- [Ron Jeffries, Card, Conversation, Confirmation](https://ronjeffries.com/xprog/articles/expcardconversationconfirmation/): clarify with examples, then confirm the agreed behavior with an acceptance check. This is why review and evidence are separate.
- [Bill Wake, INVEST in Good Stories](https://xp123.com/invest-in-good-stories-and-smart-tasks/) and [Lucassen et al., Quality User Story framework](https://doi.org/10.1007/s00766-016-0250-x): keep each story focused, valuable, and testable; look for overlaps before creating another record.
- [Ruiz, Hu, and Dalpiaz, Why don’t we trace?](https://doi.org/10.1007/s00766-023-00408-9): the effort of maintaining trace links is a practical barrier. Our design keeps direct story-to-module and check-to-evidence links and derives the view from them.
- [Coleman and Vacanti, The Kanban Guide](https://kanbanguides.org/the-kanban-guide/2025.5/pdf/kanban-guide.v2025.5.en.pdf): make state policies explicit, control started work, and use age to find stalled items.
