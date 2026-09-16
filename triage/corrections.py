"""Applies human-reviewed manual corrections on top of the pipeline's
automatic classification, as a final, auditable layer.

Corrections are kept as an explicit, separate list (see the corrections
file passed to apply_corrections) rather than hand-edited into the
generated output files, so the override, its reasoning, and what it
replaced all stay traceable. This function is reusable: any future audit
pass on any inbox can produce a corrections file in this shape and re-apply
it the same way, without needing to re-run the LLM.

apply_corrections is idempotent: the manual-corrections file is meant to be
the cumulative, growing record of every correction made across a review, and
re-running it against already-corrected records (e.g. after adding new
entries) must not re-log or re-diff corrections that were already applied.
A correction is treated as already-applied if a log entry citing the same
id and reason is already present in that record's overrides_applied.
"""


def apply_corrections(records: list[dict], corrections: list[dict]) -> list[dict]:
    by_id = {r["id"]: r for r in records}
    for c in corrections:
        rec = by_id.get(c["id"])
        if rec is None:
            continue
        rec.setdefault("overrides_applied", [])
        tag = f"MANUAL CORRECTION ({c['reason']})"
        if any(entry.startswith(tag) for entry in rec["overrides_applied"]):
            continue
        before = {k: rec.get(k) for k in c["fields"]}
        rec.update(c["fields"])
        change_summary = ", ".join(f"{k}: {before[k]!r} -> {v!r}" for k, v in c["fields"].items())
        rec["overrides_applied"] = rec["overrides_applied"] + [f"{tag} [{change_summary}]"]
    return [by_id[r["id"]] for r in records]
