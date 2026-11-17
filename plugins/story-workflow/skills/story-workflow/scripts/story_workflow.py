#!/usr/bin/env python3
"""Create, find, attach media to, or validate Git-backed Storyboard records."""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

STORY_FIELDS = "id title actor goal benefit review state modules acceptance proof"
PROOF_FIELDS = "checks kind path revision environment observed_on observation"
MODULE_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
STORY_ID = re.compile(r"US-(?:00[1-9]|0[1-9][0-9]|[1-9][0-9]{2,}|r[0-9a-f]{16})")
CHECK_ID = re.compile(r"A[1-9][0-9]*")
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
STATES = {"later", "planned", "building", "works"}
SUFFIXES = {"log": {".txt", ".log"}, "image": {".png", ".jpg", ".jpeg", ".webp"}}
MAX_PROOF_BYTES = 5 * 1024 * 1024
MAX_MEDIA_BYTES = 20 * 1024 * 1024
MAX_DIAGRAM_CHARS = 16_000
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf",
                  ".mp4", ".webm", ".mp3", ".ogg", ".wav", ".txt", ".md"}
DEFAULT_CATEGORY = "user-story"
DEFAULT_CATEGORIES = {
    DEFAULT_CATEGORY: "User story", "bug": "Bug", "technical": "Technical work", "research": "Research"
}


def require(condition, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def read_json(path: Path):
    require(path.is_file() and not path.is_symlink(), f"{path}: expected a regular JSON file")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def record(value, fields: str, where: str, optional: str = "") -> None:
    required = set(fields.split())
    require(isinstance(value, dict) and required <= set(value) <= required | set(optional.split()),
            f"{where}: expected fields {fields}" + (f" (optional: {optional})" if optional else ""))


def nonempty(value, where: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{where}: expected nonempty text")
    value.encode("utf-8")
    return value


def git_root() -> Path | None:
    try:
        result = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                capture_output=True, check=False)
    except FileNotFoundError:
        return None
    if result.returncode == 0:
        return Path(result.stdout.decode(sys.getfilesystemencoding(), "surrogateescape").rstrip("\r\n"))
    return None


def default_database() -> Path:
    root = git_root()
    if root is None:
        return Path("stories")
    current = Path.cwd()
    # Keep working with Storyboards created in a subdirectory by earlier versions.
    for folder in (current, *current.parents):
        candidate = folder / "stories"
        if (candidate / "modules.json").is_file() or folder == root:
            return candidate
    return root / "stories"


def unique_list(value, where: str) -> set[str]:
    require(isinstance(value, list) and all(isinstance(item, str) for item in value),
            f"{where}: expected an array of strings")
    result = set(value)
    require(len(result) == len(value), f"{where}: duplicate values")
    return result


def asset_path(db: Path, value, root: str, story_id: str, extensions: set[str], where: str) -> Path:
    source = PurePosixPath(nonempty(value, where))
    require(len(source.parts) == 3 and source.parts[:2] == (root, story_id)
            and source.as_posix() == value and FILE_NAME.fullmatch(source.name)
            and source.suffix.lower() in extensions,
            f"{where}: use {root}/{story_id}/<filename> with a supported extension")
    parent = db / root
    folder = parent / story_id
    path = folder / source.name
    require(not any(part.is_symlink() for part in (parent, folder, path)),
            f"{where}: symbolic links are unsupported: {source}")
    return path


def check_file(path: Path, max_bytes: int, where: str) -> None:
    require(path.is_file(), f"{where}: missing file: {path.name}")
    require(0 < path.stat().st_size <= max_bytes, f"{where}: file must be 1 byte to {max_bytes // 1024**2} MiB")


def check_publish(item: dict, where: str) -> None:
    require(isinstance(item.get("publish", False), bool), f"{where}.publish: expected true or false")


def check_https(value: str, where: str) -> None:
    require(not any(character.isspace() or ord(character) < 32 or character == "\\" for character in value),
            f"{where}: URL contains whitespace or an unsupported character")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.hostname and parsed.username is None and parsed.password is None,
            f"{where}: use an HTTPS URL without credentials")
    # Accessing port checks the syntax and range.
    _ = parsed.port


def validate_attachments(db: Path, items, story_id: str, where: str) -> None:
    require(isinstance(items, list), f"{where}: expected an array")
    seen = set()
    for index, item in enumerate(items):
        field = f"{where}[{index}]"
        record(item, "label target", field, optional="publish")
        nonempty(item["label"], f"{field}.label")
        check_publish(item, field)
        target = nonempty(item["target"], f"{field}.target")
        if target.startswith("media/"):
            path = asset_path(db, target, "media", story_id, MEDIA_SUFFIXES, f"{field}.target")
            check_file(path, MAX_MEDIA_BYTES, f"{field}.target")
        else:
            check_https(target, f"{field}.target")
        require(target not in seen, f"{field}.target: already attached")
        seen.add(target)


def validate_proof(db: Path, item, story_id: str, check_ids: set[str], where: str) -> set[str]:
    record(item, PROOF_FIELDS, where, optional="publish")
    check_publish(item, where)
    checks = unique_list(item["checks"], f"{where}.checks")
    require(checks and checks <= check_ids, f"{where}.checks: name existing acceptance checks")
    kind = nonempty(item["kind"], f"{where}.kind")
    require(kind in SUFFIXES, f"{where}.kind: use log or image")
    path = asset_path(db, item["path"], "evidence", story_id, SUFFIXES[kind], f"{where}.path")
    check_file(path, MAX_PROOF_BYTES, f"{where}.path")
    if kind == "log":
        content = path.read_text(encoding="utf-8")
        require(content.strip() and "\x00" not in content, f"{where}.path: use a plain text log")
    else:
        with path.open("rb") as stream:
            head = stream.read(12)
        signature = {
            ".png": head.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": head.startswith(b"\xff\xd8\xff"),
            ".jpeg": head.startswith(b"\xff\xd8\xff"),
            ".webp": head.startswith(b"RIFF") and head[8:12] == b"WEBP",
        }
        require(signature[path.suffix.lower()], f"{where}.path: bytes do not match the image extension")
    for field in ("revision", "environment", "observation"):
        nonempty(item[field], f"{where}.{field}")
    observed_on = nonempty(item["observed_on"], f"{where}.observed_on")
    try:
        require(date.fromisoformat(observed_on).isoformat() == observed_on, "noncanonical date")
    except ValueError as exc:
        raise ValueError(f"{where}.observed_on: use a real date in YYYY-MM-DD form") from exc
    return checks


def validate_story(db: Path, story, path: Path, catalog: dict[str, str], categories: dict[str, str]) -> None:
    where = path.name
    record(story, STORY_FIELDS, where, optional="category details attachments")
    story_id = nonempty(story["id"], f"{where}.id")
    require(STORY_ID.fullmatch(story_id) and path.name == f"{story_id}.json",
            f"{where}: id must match the canonical filename")
    for field in ("title", "actor", "goal", "benefit"):
        nonempty(story[field], f"{where}.{field}")
    category = nonempty(story.get("category", DEFAULT_CATEGORY), f"{where}.category")
    require(category in categories, f"{where}.category: unregistered category {category!r}")
    details = story.get("details", "")
    require(isinstance(details, str), f"{where}.details: expected text")
    details.encode("utf-8")
    validate_attachments(db, story.get("attachments", []), story_id, f"{where}.attachments")
    state = nonempty(story["state"], f"{where}.state")
    require(state in STATES, f"{where}.state: use later, planned, building, or works")
    require(story["review"] in ("proposed", "agreed"), f"{where}.review: use proposed or agreed")
    modules = unique_list(story["modules"], f"{where}.modules")
    missing = modules - catalog.keys()
    require(not missing, f"{where}.modules: unregistered IDs: {', '.join(sorted(missing))}")
    require(isinstance(story["acceptance"], list), f"{where}.acceptance: expected an array")
    checks = set()
    for i, check in enumerate(story["acceptance"]):
        field = f"{where}.acceptance[{i}]"
        record(check, "id text", field)
        check_id = nonempty(check["id"], f"{field}.id")
        require(CHECK_ID.fullmatch(check_id) and check_id not in checks, f"{field}.id: use a unique A-number")
        checks.add(check_id)
        nonempty(check["text"], f"{field}.text")
    if state in ("building", "works"):
        require(story["review"] == "agreed" and checks,
                f"{where}: {state} requires agreement and acceptance checks")

    require(isinstance(story["proof"], list), f"{where}.proof: expected an array")
    covered = set()
    artifacts = set()
    for i, item in enumerate(story["proof"]):
        field = f"{where}.proof[{i}]"
        covered.update(validate_proof(db, item, story_id, checks, field))
        require(item["path"] not in artifacts, f"{field}.path: repeated artifact; combine its check IDs")
        artifacts.add(item["path"])
    if state == "works":
        missing_checks = checks - covered
        require(not missing_checks, f"{where}: Works is missing proof for {', '.join(sorted(missing_checks))}")


def load_catalog(path: Path) -> dict[str, str]:
    catalog = read_json(path)
    require(isinstance(catalog, dict), f"{path.name}: expected an object mapping IDs to labels")
    for name, label in catalog.items():
        require(MODULE_ID.fullmatch(name), f"{path.name}: invalid ID {name!r}")
        nonempty(label, f"{path.name}: label for {name}")
    return catalog


def load_categories(db: Path) -> dict[str, str]:
    path = db / "categories.json"
    if not path.exists() and not path.is_symlink():
        return DEFAULT_CATEGORIES.copy()
    categories = load_catalog(path)
    require(DEFAULT_CATEGORY in categories, f"{path.name}: include {DEFAULT_CATEGORY!r} for existing records")
    return categories


def load_db(db: Path) -> tuple[dict[str, str], list[dict]]:
    db = db.resolve()
    folders = db / "items"
    require(not folders.is_symlink() and (not folders.exists() or folders.is_dir()),
            f"{folders}: expected a regular directory")
    catalog = load_catalog(db / "modules.json")
    categories = load_categories(db)
    stories = []
    for path in sorted(folders.glob("*.json")):
        story = read_json(path)
        validate_story(db, story, path, catalog, categories)
        story.setdefault("category", DEFAULT_CATEGORY)
        story.setdefault("details", "")
        story.setdefault("attachments", [])
        stories.append(story)
    return catalog, sorted(stories, key=lambda story: (len(story["id"]), story["id"]))


def load_diagrams(db: Path, stories: list[dict]) -> dict[str, str]:
    folder = db / "diagrams"
    require(not folder.is_symlink() and (not folder.exists() or folder.is_dir()),
            f"{folder}: expected a regular directory")
    ids = {story["id"] for story in stories}
    diagrams = {}
    for path in sorted(folder.glob("*.mmd")):
        require(path.stem in ids, f"{path.name}: diagram must name an existing record ID")
        require(path.is_file() and not path.is_symlink(), f"{path.name}: expected a regular Mermaid file")
        with path.open(encoding="utf-8") as source:
            text = source.read(MAX_DIAGRAM_CHARS + 1)
        require(0 < len(text) <= MAX_DIAGRAM_CHARS and text.strip() and "\x00" not in text,
                f"{path.name}: expected Mermaid source up to {MAX_DIAGRAM_CHARS:,} characters")
        require(not text.lstrip().startswith("---") and "%%{" not in text,
                f"{path.name}: use Mermaid diagram syntax without front matter or directives")
        diagrams[path.stem] = text.strip()
    return diagrams


def write_exclusive(path: Path, value) -> None:
    content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)


def initialize(db: Path) -> None:
    (db / "items").mkdir(parents=True, exist_ok=True)
    catalog = db / "modules.json"
    try:
        write_exclusive(catalog, {})
    except FileExistsError:
        pass
    load_db(db)


def find_stories(stories: list[dict], query: str, category: str | None) -> None:
    term = nonempty(query, "search query").strip().casefold()
    tokens = set(re.findall(r"\w+", term))
    matches = []
    for story in stories:
        if category and story["category"] != category:
            continue
        title = story["title"].casefold()
        content = " ".join(story[key] for key in ("title", "actor", "goal", "benefit", "details")).casefold()
        if term == story["id"].casefold() or term == title:
            score = (3, 0)
        elif term in content:
            score = (2, 0)
        else:
            overlap = tokens.intersection(re.findall(r"\w+", content))
            if not overlap:
                continue
            score = (1, len(overlap))
        matches.append((score, story))
    if not matches:
        print("No matching records.")
    for _, story in sorted(matches, key=lambda match: match[0], reverse=True)[:15]:
        print(f"{story['id']}\t{story['category']}\t{story['state']}\t{story['title']}")


def copy_attachment(db: Path, story_id: str, source: Path) -> Path:
    check_file(source, MAX_MEDIA_BYTES, str(source))
    extension = source.suffix.lower()
    require(extension in MEDIA_SUFFIXES, f"{source.name}: unsupported file type; attach an HTTPS link instead")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip(".-_")[:80] or "attachment"
    number = 1
    while True:
        suffix = "" if number == 1 else f"-{number}"
        relative = f"media/{story_id}/{stem}{suffix}{extension}"
        target = asset_path(db, relative, "media", story_id, MEDIA_SUFFIXES, "attachment")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            output = target.open("xb")
        except FileExistsError:
            number += 1
            continue
        try:
            with output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target


def save_story(path: Path, story: dict, original: bytes) -> None:
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, mode="w", encoding="utf-8", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(story, indent=2, ensure_ascii=False) + "\n")
        temporary.chmod(path.stat().st_mode & 0o777)
        require(path.read_bytes() == original, f"{path.name}: changed while attaching; retry")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def attach(db: Path, story_id: str, source: str, label: str | None, publish: bool,
           catalog: dict[str, str], categories: dict[str, str]) -> str:
    require(STORY_ID.fullmatch(story_id), "use a Storyboard record ID")
    path = db / "items" / f"{story_id}.json"
    require(path.is_file() and not path.is_symlink(), f"{path.name}: record not found")
    lock = path.with_name(f".{story_id}.lock")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError(f"{story_id}: attachment update in progress; retry after it finishes") from exc
    try:
        return attach_to_record(db, path, source, label, publish, catalog, categories)
    finally:
        lock.rmdir()


def attach_to_record(db: Path, path: Path, source: str, label: str | None, publish: bool,
                     catalog: dict[str, str], categories: dict[str, str]) -> str:
    original = path.read_bytes()
    story = json.loads(original.decode("utf-8"), object_pairs_hook=unique_object)
    validate_story(db, story, path, catalog, categories)
    local_copy = None
    try:
        if "://" in source:
            check_https(source, "attachment")
            target = source
            default_label = urlsplit(source).hostname
        else:
            local_copy = copy_attachment(db, path.stem, Path(source))
            target = local_copy.relative_to(db).as_posix()
            default_label = Path(source).name
        story.setdefault("attachments", []).append(
            {"label": default_label if label is None else label, "target": target, "publish": publish})
        validate_story(db, story, path, catalog, categories)
        save_story(path, story, original)
        return target
    except BaseException:
        if local_copy is not None:
            local_copy.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="database directory (default: stories in the Git repo)")
    sub = parser.add_subparsers(dest="command", required=True)
    bootstrap = sub.add_parser("bootstrap", help="set up Git storage and a dashboard in this repository")
    bootstrap.add_argument("--pages", action="store_true", help="prepare automatic GitHub Pages deployment")
    preview = sub.add_parser("preview", help="rebuild the local dashboard")
    preview.add_argument("--serve", action="store_true", help="serve the preview on localhost")
    preview.add_argument("--include-proof", action="store_true", help="show unpublished proof in the local preview")
    preview.add_argument("--include-media", action="store_true", help="show unpublished attachments in the local preview")
    sub.add_parser("init", help="create an empty collection")
    sub.add_parser("check", help="validate stories, module links, and proof")
    sub.add_parser("jsonl", help="export all records as JSON Lines to stdout, including private references")
    find = sub.add_parser("find", help="look for an existing record before creating one")
    find.add_argument("query")
    find.add_argument("--category")
    new = sub.add_parser("new", help="create one proposed Storyboard record")
    for arg in ("title", "actor", "goal", "benefit"):
        new.add_argument(f"--{arg}", required=True)
    new.add_argument("--category", default=DEFAULT_CATEGORY)
    new.add_argument("--details", default="")
    add_media = sub.add_parser("attach", help="attach a local file or HTTPS link")
    add_media.add_argument("story_id")
    add_media.add_argument("source")
    add_media.add_argument("--label")
    add_media.add_argument("--publish", action="store_true", help="include in the default Pages export")
    args = parser.parse_args()
    try:
        args.db = args.db or default_database()
        if args.command in ("bootstrap", "preview"):
            from setup_board import bootstrap_board, preview_board

            if args.command == "bootstrap":
                bootstrap_board(args.db, args.pages)
            else:
                preview_board(args.db, args.include_proof, args.include_media, args.serve)
            return 0
        if args.command == "init":
            initialize(args.db)
            print(f"Story collection ready at {args.db}")
            return 0
        db = args.db.resolve()
        catalog, stories = load_db(db)
        categories = load_categories(db)
        if args.command == "check":
            diagrams = load_diagrams(db, stories)
            print(f"Validated {len(stories)} records, {len(catalog)} modules, "
                  f"{len(categories)} categories, and {len(diagrams)} diagram files")
        elif args.command == "find":
            require(args.category is None or args.category in categories, f"unknown category {args.category!r}")
            find_stories(stories, args.query, args.category)
        elif args.command == "jsonl":
            for story in stories:
                line = json.dumps(story, ensure_ascii=False, separators=(",", ":"))
                sys.stdout.buffer.write((line + "\n").encode("utf-8"))
        elif args.command == "attach":
            print(attach(db, args.story_id, args.source, args.label, args.publish, catalog, categories))
        else:
            story = {"id": f"US-r{secrets.token_hex(8)}",
                     **{field: getattr(args, field) for field in ("title", "actor", "goal", "benefit")},
                     "category": args.category, "details": args.details,
                     "review": "proposed", "state": "planned", "modules": [], "acceptance": [], "proof": [],
                     "attachments": []}
            target = args.db / "items" / f"{story['id']}.json"
            validate_story(db, story, target, catalog, categories)
            target.parent.mkdir(exist_ok=True)
            write_exclusive(target, story)
            print(target)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
