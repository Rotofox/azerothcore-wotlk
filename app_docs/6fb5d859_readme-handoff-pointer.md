# Documentation README — Fury/NexusFrames handoff pointer

## What changed

`documentation/README.md` gained a **"Working docs"** section (4 lines, appended after the
"Status flags" section) that links `documentation/fury-nexusframes-handoff.md` and describes it
as the agent handoff for the **Fury system + NexusFrames** feature (account-wide kill-based
progression + its UI addon), pointing onward to `specs/fury-nexusframes-design.md` as the design
home.

That is the only tracked change in this diff: `+4 -0` across one file.

## Why it matters

The onboarding README previously indexed only the general repo docs (build/run, architecture,
data layer, modules, divergences). The Fury/NexusFrames work was documented in a standalone
handoff that was not discoverable from the docs entry point. This change makes the handoff a
first-class working doc: a new agent reading `documentation/` top-to-bottom now lands on the
Fury handoff instead of hunting for it.

The handoff file it links (`documentation/fury-nexusframes-handoff.md`) is an untracked work
product in the working tree, not part of this diff's tracked change. It contains the verified
code locations (script hooks, haste/AP/SP/stat APIs, account id, addon-channel transport),
the gotchas that bit earlier runs (MySQL 8 reserved words, WDB cache rule, no SP% in this fork,
modules are gitignored clones), the deliverable map, and the open build-time items from the
design spec §5.

## Files that carry it

- `documentation/README.md` — the tracked change (new "Working docs" section).
- `documentation/fury-nexusframes-handoff.md` — the linked handoff (untracked; referenced by
  the new section).
- `specs/fury-nexusframes-design.md` — the authoritative design the section points to.

## How to use / verify

1. Open `documentation/README.md` and confirm the "Working docs" section lists
   `fury-nexusframes-handoff.md` with the "Agent handoff for the Fury system + NexusFrames
   feature" description.
2. Follow the link; the handoff exists and covers the feature's facts, gotchas, deliverable
   locations, and open build-time items.
3. Note that the README's earlier "Repository state" claim ("Working tree clean at HEAD
   `1507ab3f`") predates this edit; the working tree now carries the untracked Fury project
   tree (specs, requests, addon sources, example addons, DBCs, prior write-ups) on top of the
   tracked HEAD `d977fa994`.

## Scope notes

This write-up documents the tracked README change only. The `prompt` describes a larger v2
build (addon minimap button, spec-aware modules, suffix-boost tooling, variant pricing); none
of those deliverables appear in this diff and this write-up does not claim them. No git
operations were performed; the change exists only in the working tree.
