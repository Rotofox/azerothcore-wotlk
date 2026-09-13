#!/usr/bin/env python3
"""Verify the machine-checkable project facts in documentation/state.json against the live tree.

Why this exists: the onboarding docs drifted because volatile facts (HEAD hashes, module counts,
patch filenames, DB counts) were written into prose. `documentation/` is now the single source of
truth and `documentation/state.json` holds the small set of facts a script can re-derive. Run this
after any change that could touch one of those facts (see AGENTS.md).

Usage:
    python3 apps/codestyle/check-docs.py

Exit code 0 = all checks pass (or were skipped because the relevant tree is absent, e.g. a fresh
clone with no modules/). Exit code 1 = drift; each FAIL line names the file/fact to fix.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "documentation" / "state.json"

failures: list[str] = []
skips: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def skip(msg: str) -> None:
    skips.append(msg)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def check_branch(state: dict) -> None:
    head = read_text(ROOT / ".git" / "HEAD")
    if head is None:
        skip("branch: no .git (not a git checkout)")
        return
    head = head.strip()
    if head.startswith("ref: refs/heads/"):
        branch = head[len("ref: refs/heads/"):]
    else:
        branch = head  # detached HEAD
    expected = state["branch"]
    if branch != expected:
        fail(f"branch: state.json says '{expected}', .git/HEAD says '{branch}'")


def check_data_version(state: dict) -> None:
    text = read_text(ROOT / "env" / "dist" / "bin" / "data-version")
    if text is None:
        skip("client_data_version: env/dist/bin/data-version not present")
        return
    m = re.search(r"INSTALLED_VERSION=(\S+)", text)
    if not m:
        fail("client_data_version: env/dist/bin/data-version has no INSTALLED_VERSION=")
        return
    expected = state["client_data_version"]
    if m.group(1) != expected:
        fail(
            f"client_data_version: state.json says '{expected}', "
            f"env/dist/bin/data-version says '{m.group(1)}'"
        )


def _conf_option(path: Path, key: str) -> str | None:
    text = read_text(path)
    if text is None:
        return None
    m = re.search(rf"^\s*{re.escape(key)}\s*=\s*(\S+)", text, re.MULTILINE)
    return m.group(1) if m else None


def check_ports(state: dict) -> None:
    checks = [
        ("worldserver", ROOT / "env" / "dist" / "etc" / "worldserver.conf", "WorldServerPort"),
        ("authserver", ROOT / "env" / "dist" / "etc" / "authserver.conf", "RealmServerPort"),
    ]
    for name, path, key in checks:
        got = _conf_option(path, key)
        if got is None:
            skip(f"port {name}: {path.relative_to(ROOT)} not present")
            continue
        want = str(state["ports"][name])
        if got != want:
            fail(f"port {name}: state.json says {want}, {path.name} {key} = {got}")


def check_databases(state: dict) -> None:
    core_sql = read_text(ROOT / "data" / "sql" / "create" / "create_mysql.sql")
    if core_sql is None:
        skip("databases: data/sql/create/create_mysql.sql not present")
    else:
        for db in state["databases"]:
            if db == "acore_playerbots":
                continue
            if db not in core_sql:
                fail(f"databases: '{db}' not found in data/sql/create/create_mysql.sql")
    pb_sql = read_text(
        ROOT / "modules" / "mod-playerbots" / "data" / "sql" / "playerbots"
        / "create" / "create_mysql.sql"
    )
    if pb_sql is None:
        skip("databases: mod-playerbots create script not present (module tree empty?)")
    elif "acore_playerbots" not in pb_sql:
        fail("databases: 'acore_playerbots' not found in mod-playerbots create script")


def present_modules() -> set[str] | None:
    mods_dir = ROOT / "modules"
    if not mods_dir.is_dir():
        return None
    found = set()
    for d in mods_dir.iterdir():
        if d.is_dir() and d.name.startswith("mod-") and (d / "src").is_dir():
            found.add(d.name)
    return found


def check_modules(state: dict) -> None:
    present = present_modules()
    if not present:
        skip("modules: no module dirs with src/ present (fresh clone?)")
        return
    want_clones = set(state["modules"]["clones"])
    want_local = set(state["modules"]["local"])
    expected = want_clones | want_local

    for extra in sorted(present - expected):
        fail(f"modules: '{extra}' is present but not listed in state.json -> {STATE_PATH.name}")
    for missing in sorted(expected - present):
        fail(f"modules: '{missing}' listed in state.json but not present on disk")
    for name in sorted(want_clones & present):
        if not (ROOT / "modules" / name / ".git").exists():
            fail(f"modules: '{name}' is listed as a git clone but has no .git")
    for name in sorted(want_local & present):
        if (ROOT / "modules" / name / ".git").exists():
            fail(f"modules: '{name}' is listed as local/untracked but has a .git")


def check_client_addons(state: dict) -> None:
    cr = ROOT / "client-resources"
    if not cr.is_dir():
        skip("client_addons: client-resources/ not present")
        return
    found = {d.name for d in cr.iterdir() if d.is_dir() and list(d.glob("*.toc"))}
    expected = set(state["client_addons"])
    known = expected | set(state.get("client_addons_reference", []))
    for extra in sorted(found - known):
        fail(f"client_addons: addon '{extra}' found but not listed in state.json")
    for missing in sorted(expected - found):
        fail(f"client_addons: addon '{missing}' listed in state.json but no *.toc found")


PATCH_RE = re.compile(r"patch-(?:[5-9]|[1-9][0-9])\.mpq", re.IGNORECASE)


def check_single_patch() -> None:
    """The client uses one consolidated patch (patch-4.MPQ). No doc may reference patch-5+."""
    roots = [ROOT / "documentation", ROOT / "client-resources", ROOT / "specs", ROOT / ".agents"]
    files = [ROOT / "AGENTS.md"]
    for r in roots:
        if r.is_dir():
            files.extend(r.rglob("*.md"))
    for f in files:
        text = read_text(f)
        if not text:
            continue
        for m in PATCH_RE.finditer(text):
            fail(f"single-patch: {f.relative_to(ROOT)} references '{m.group(0)}' (use patch-4.MPQ)")


def check_source_of_truth_docs(state: dict) -> None:
    for rel in state["source_of_truth_docs"]:
        if not (ROOT / rel).is_file():
            fail(f"source_of_truth_docs: '{rel}' listed in state.json but missing")


def main() -> int:
    if not STATE_PATH.is_file():
        print(f"FAIL: {STATE_PATH} not found")
        return 1
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"FAIL: cannot parse {STATE_PATH}: {e}")
        return 1

    check_branch(state)
    check_data_version(state)
    check_ports(state)
    check_databases(state)
    check_modules(state)
    check_client_addons(state)
    check_single_patch()
    check_source_of_truth_docs(state)

    for s in skips:
        print(f"SKIP: {s}")
    for f in failures:
        print(f"FAIL: {f}")

    if failures:
        print(f"\n{len(failures)} drift problem(s). Fix the doc or the tree, then re-run.")
        return 1
    print("\nOK: documentation/state.json matches the tree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
