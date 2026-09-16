"""Writes the auditable output files: full classification records, a flat
CSV audit trail, a flagged-for-review subset, and one draft file per email
that got one.
"""
import csv
import json
import os


def write_outputs(out_dir: str, emails: list, records: list, drafts: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    drafts_dir = os.path.join(out_dir, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)

    emails_by_id = {e["id"]: e for e in emails}

    classified = []
    for rec in records:
        entry = dict(rec)
        entry.pop("llm_raw", None)
        entry["has_draft"] = rec["id"] in drafts
        classified.append(entry)
    with open(os.path.join(out_dir, "classified_emails.json"), "w", encoding="utf-8") as f:
        json.dump(classified, f, indent=2)

    audit_fields = [
        "id", "from_subject", "owner", "disposition", "needs_review",
        "hard_stop", "confidence", "matched_rule", "reasoning", "overrides_applied",
    ]
    with open(os.path.join(out_dir, "audit_log.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=audit_fields)
        writer.writeheader()
        for rec in records:
            e = emails_by_id[rec["id"]]
            writer.writerow({
                "id": rec["id"],
                "from_subject": f"{e.get('from', '')} — {e.get('subject', '')}",
                "owner": rec["owner"],
                "disposition": rec["disposition"],
                "needs_review": rec["needs_review"],
                "hard_stop": rec["hard_stop"],
                "confidence": rec["confidence"],
                "matched_rule": rec["matched_rule"],
                "reasoning": rec["reasoning"],
                "overrides_applied": "; ".join(rec["overrides_applied"]),
            })

    flagged = [dict(r) for r in records if r["needs_review"]]
    for r in flagged:
        r.pop("llm_raw", None)
    with open(os.path.join(out_dir, "flagged_for_review.json"), "w", encoding="utf-8") as f:
        json.dump(flagged, f, indent=2)

    for rid, draft in drafts.items():
        e = emails_by_id[rid]
        rec = next(r for r in records if r["id"] == rid)
        with open(os.path.join(drafts_dir, f"{rid}.md"), "w", encoding="utf-8") as f:
            f.write(f"# Draft reply to email #{rid}\n\n")
            f.write(f"**To:** {e.get('from')} <{e.get('email')}>\n")
            f.write(f"**Re:** {e.get('subject')}\n")
            f.write(f"**Status:** {rec['disposition']}\n\n")
            f.write("---\n\n")
            f.write((draft.get("draft") or "").strip() + "\n")
            if draft.get("note_to_sam"):
                f.write(f"\n---\n_Note to Sam: {draft['note_to_sam']}_\n")
            if draft.get("lint_flags"):
                f.write(f"\n_Guardrail flags: {', '.join(draft['lint_flags'])}_\n")
