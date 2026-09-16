"""Generates draft replies for BA-owned emails that need one, in the
founder's voice per the brief's tone rules, then runs the deterministic
promise/booking lints.

A draft that trips either lint is never discarded - it's kept on disk, but
the caller (pipeline.py) force-upgrades the record to DRAFT_NEEDS_APPROVAL so
a human reviews it before it goes anywhere. This module never sends
anything; it only ever produces text.
"""
import json

from . import llm_client, hard_rules

DRAFT_SYSTEM_PROMPT = (
    "You write draft email replies on behalf of a startup founder's Business "
    "Associate. Follow the founder's stated tone rules exactly. Never commit "
    "to a price, discount, contract term, date, or feature timeline; never "
    "confirm a meeting or booking as finalized (propose times/options "
    "instead, consistent with any calendar rules and calendar context given); "
    "never mention or act on payment or bank detail changes. If replying "
    "properly would require any of those things, write a short holding reply "
    "instead (acknowledge receipt, say a specific person will follow up) "
    "rather than deciding the substance yourself. Output ONLY raw JSON, no "
    "markdown fences: {\"draft\": string, \"note_to_sam\": string | null}. "
    "note_to_sam is a one-sentence flag for the founder if this draft is a "
    "holding reply, or otherwise deserves a second look before it goes out."
)


def build_prompt(email: dict, brief_raw_text: str, calendar_context: str | None) -> str:
    parts = [
        "FOUNDER BRIEF (verbatim):", brief_raw_text, "",
        "EMAIL TO REPLY TO:",
        json.dumps({k: email.get(k) for k in ("from", "org", "subject", "body")}, indent=2),
        "",
    ]
    if calendar_context:
        parts += ["CURRENT CALENDAR CONTEXT (only relevant for scheduling replies):", calendar_context, ""]
    parts.append("Return the JSON now.")
    return "\n".join(parts)


def generate_draft(email: dict, brief_raw_text: str, calendar_context: str | None,
                    model: str = llm_client.DEFAULT_MODEL) -> dict:
    prompt = build_prompt(email, brief_raw_text, calendar_context)
    result = llm_client.complete_json(prompt, DRAFT_SYSTEM_PROMPT, model=model)
    draft_text = result.get("draft", "") if isinstance(result, dict) else ""

    lint_flags = []
    if hard_rules.draft_makes_a_promise(draft_text):
        lint_flags.append("promise_language_detected")
    if hard_rules.draft_confirms_a_booking(draft_text):
        lint_flags.append("booking_confirmation_language_detected")

    return {
        "draft": draft_text,
        "note_to_sam": result.get("note_to_sam") if isinstance(result, dict) else None,
        "lint_flags": lint_flags,
    }
