"""Check the marketplace layout and bootstrap the dashboard in a fresh Git repo."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    entry = marketplace["plugins"][0]
    plugin = ROOT / entry["source"]["path"]
    manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == entry["name"]
    skill = plugin / manifest["skills"] / "story-workflow"
    assert (skill / "SKILL.md").is_file()
    cli = skill / "scripts/story_workflow.py"
    sample = plugin / "examples/stories"

    with TemporaryDirectory(prefix="storyboard-smoke-") as temporary:
        workspace = Path(temporary)
        site = workspace / "sample"
        run(sys.executable, "-B", cli, "--db", sample, "check")
        run(sys.executable, "-B", cli.with_name("export_pages.py"), "--db", sample, "--out", site)
        assert "Download an invoice" in (site / "index.html").read_text(encoding="utf-8")
        assert (site / "assets/mermaid/mermaid.min.js").is_file()
        assert (site / "evidence/US-001/download-example.txt").is_file()

        repo = workspace / "checkout"
        run("git", "init", "-qb", "trunk", repo)
        nested = repo / "app"
        nested.mkdir()
        run(sys.executable, "-B", cli, "bootstrap", "--pages", cwd=nested)
        workflow = repo / ".github/workflows/storyboard-pages.yml"
        before = workflow.read_bytes()
        runtime = repo / "tools/storyboard/scripts/story_workflow.py"
        run(sys.executable, "-B", runtime, "bootstrap", "--pages", cwd=nested)
        assert workflow.read_bytes() == before
        run("git", "check-ignore", "_storyboard/index.html", cwd=repo)
        run(sys.executable, "-B", runtime, "new", "--title", "Track delivery", "--actor", "Reviewer",
            "--goal", "See delivery state", "--benefit", "Prioritize open work", cwd=nested)
        run(sys.executable, "-B", runtime, "preview", cwd=nested)
        assert "Track delivery" in (repo / "_storyboard/index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
