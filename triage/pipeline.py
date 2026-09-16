"""End-to-end orchestration: load -> classify -> route -> draft -> audit -> brief.

Classification calls run in parallel (LLM calls are I/O-bound), then draft
generation runs in parallel for whatever the router decided is BA-owned and
reply-needed. Every stage's failure mode defaults toward escalating to Sam
rather than guessing - see router.py and the except blocks below.
"""
import concurrent.futures as cf

from . import loader, brief_parser, classifier, draft_generator, router, llm_client


def _classify_one(email: dict, brief_raw_text: str, model: str) -> dict:
    try:
        llm_out = classifier.classify_email(email, brief_raw_text, model=model)
        error = None
    except llm_client.LLMError as e:
        llm_out = {}
        error = str(e)
    record = router.resolve(email, llm_out)
    if error:
        print(f"LLM classification failed for email {email['id']}: {error}")
        record["overrides_applied"].append(
            f"LLM classification failed ({error}); defaulted to SAM/low-confidence"
        )
    return record


def _draft_one(email: dict, record: dict, brief_raw_text: str, calendar_context, model: str):
    try:
        draft = draft_generator.generate_draft(email, brief_raw_text, calendar_context, model=model)
    except llm_client.LLMError as e:
        record["overrides_applied"].append(f"draft generation failed ({e}); no draft produced, escalated to Sam")
        record["owner"] = "SAM"
        record["needs_review"] = True
        record["disposition"] = "SAM_PERSONAL"
        return None

    if draft["lint_flags"]:
        if record["disposition"] == "DRAFT_NO_APPROVAL":
            record["overrides_applied"].append(
                f"draft lint tripped ({', '.join(draft['lint_flags'])}); upgraded to DRAFT_NEEDS_APPROVAL"
            )
        record["needs_sam_approval"] = True
        record["disposition"] = "DRAFT_NEEDS_APPROVAL"
    return draft


def run(emails_path: str, brief_path: str, model: str = llm_client.DEFAULT_MODEL, max_workers: int = 6) -> dict:
    emails, scenario, calendar = loader.load_emails(emails_path)
    brief = brief_parser.parse_founder_brief(brief_path)
    calendar_context = loader.format_calendar_context(calendar) if calendar else None

    records: dict = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_classify_one, e, brief.raw_text, model): e["id"] for e in emails}
        for fut in cf.as_completed(futures):
            rec = fut.result()
            records[rec["id"]] = rec

    emails_by_id = {e["id"]: e for e in emails}
    draft_targets = [
        rid for rid, rec in records.items()
        if rec["owner"] == "BA" and rec["needs_reply"] and not rec["hard_stop"]
    ]

    drafts: dict = {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_draft_one, emails_by_id[rid], records[rid], brief.raw_text, calendar_context, model): rid
            for rid in draft_targets
        }
        for fut in cf.as_completed(futures):
            rid = futures[fut]
            result = fut.result()
            if result is not None:
                drafts[rid] = result

    ordered_records = [records[e["id"]] for e in emails]
    return {
        "emails": emails,
        "records": ordered_records,
        "drafts": drafts,
        "scenario": scenario,
        "brief": brief,
        "calendar": calendar,
    }
