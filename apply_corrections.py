#!/usr/bin/env python3
"""Applies a manual-corrections file on top of an already-run triage output
directory, then regenerates every dependent file (classified_emails.json,
audit_log.csv, flagged_for_review.json, briefing_1130.md) from the
corrected records, so nothing drifts out of sync. Existing draft files are
round-tripped byte-for-byte (parsed back into the same structure audit.py
expects) rather than touched, since a correction pass doesn't need to
regenerate draft text unless a correction changes what needs a draft.

Usage:
    python apply_corrections.py --out output --corrections output/manual_corrections.json
"""
import argparse
import json
import os
import re

from triage import loader, audit, briefing, corrections


def parse_existing_draft(path: str) -> dict:
    text = open(path, encoding="utf-8").read()
    _, _, rest = text.partition("\n\n---\n\n")
    note = None
    flags: list[str] = []
    m = re.search(r"\n_Guardrail flags: (.*?)_\n?$", rest)
    if m:
        flags = [x.strip() for x in m.group(1).split(",")]
        rest = rest[: m.start()]
    m = re.search(r"\n\n---\n_Note to Sam: (.*?)_\n?$", rest)
    if m:
        note = m.group(1)
        rest = rest[: m.start()]
    return {"draft": rest.strip(), "note_to_sam": note, "lint_flags": flags}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emails", default="emails_raw.json")
    parser.add_argument("--out", default="output")
    parser.add_argument("--corrections", required=True)
    args = parser.parse_args()

    emails, scenario, _calendar = loader.load_emails(args.emails)

    with open(os.path.join(args.out, "classified_emails.json"), encoding="utf-8") as f:
        records = json.load(f)
    for r in records:
        r.pop("has_draft", None)
        r.setdefault("overrides_applied", [])

    drafts_dir = os.path.join(args.out, "drafts")
    drafts = {}
    for name in sorted(os.listdir(drafts_dir)):
        if name.endswith(".md"):
            rid = int(name[: -len(".md")])
            drafts[rid] = parse_existing_draft(os.path.join(drafts_dir, name))

    with open(args.corrections, encoding="utf-8") as f:
        correction_list = json.load(f)
    records = corrections.apply_corrections(records, correction_list)

    audit.write_outputs(args.out, emails, records, drafts)
    brief_md = briefing.generate_briefing(scenario, emails, records, drafts)
    with open(os.path.join(args.out, "briefing_1130.md"), "w", encoding="utf-8") as f:
        f.write(brief_md)

    print(f"Applied {len(correction_list)} correction(s); regenerated outputs in {args.out}/")


if __name__ == "__main__":
    main()
