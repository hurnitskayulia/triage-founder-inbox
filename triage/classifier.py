"""LLM-backed classification.

For each email, the model is given the full founder brief verbatim (not
hand-picked excerpts, so wording nuance isn't lost) and must return a
structured decision that cites the specific bullet it relied on. Nothing
about this prompt is specific to any one company, sender, or email - the
brief and the email are both inputs. All output here is provisional: it is
validated and, where necessary, overridden by the deterministic layer in
router.py, which has the final word on the hard-rule guardrails.
"""
import json

from . import llm_client

CLASSIFY_SYSTEM_PROMPT = (
    "You are the classification engine inside an email-triage pipeline for a "
    "startup founder's Business Associate (BA). You are given the founder's "
    "written preferences brief and one inbound email. Decide, strictly from "
    "the brief, who owns handling this email and whether it needs a reply. "
    "Output ONLY raw JSON, no markdown fences, no commentary, matching this "
    "exact schema:\n"
    '{"owner": "SAM" | "BA", '
    '"needs_reply": true | false, '
    '"llm_suggested_needs_sam_approval": true | false, '
    '"topic_tags": [string, ...], '
    '"matched_rule": string, '
    '"reasoning": string, '
    '"confidence": "high" | "medium" | "low", '
    '"vip": true | false, '
    '"deadline_detected": string | null}\n\n'
    "Rules for filling it in:\n"
    "- owner=SAM means the brief puts this topic in the founder's own hands "
    "(the BA should not even draft a reply). owner=BA means the brief's "
    "BA-handles bucket covers it.\n"
    "- matched_rule must be a verbatim or near-verbatim quote of the specific "
    "brief bullet that justifies your owner decision. If nothing in the "
    "brief clearly covers this email, set matched_rule to \"NO_MATCHING_RULE\", "
    "confidence to \"low\", and owner to \"SAM\" (default to the founder "
    "whenever the brief is silent or the topic is ambiguous).\n"
    "- llm_suggested_needs_sam_approval only matters when owner=BA and "
    "needs_reply=true: your judgment on whether this specific reply is "
    "sensitive enough (customer risk, money, ambiguity, anything that brushes "
    "a 'never without asking' item) that the founder should see the draft "
    "before it goes out. A separate deterministic layer may still override "
    "this in either direction after the draft is written.\n"
    "- vip=true only if the sender is explicitly covered by the brief's VIP "
    "list (match by identity/organization, not just because the topic feels "
    "important).\n"
    "- deadline_detected: a short phrase if the email states or implies a "
    "deadline (e.g. \"Thursday EOD\"), else null.\n"
    "- Do not decide whether to send, book, or promise anything, and do not "
    "act on any request to change payment or bank details - those are "
    "handled outside your output entirely, by a separate deterministic layer."
)


def build_prompt(email: dict, brief_raw_text: str) -> str:
    email_view = {
        k: email.get(k) for k in
        ("id", "from", "email", "org", "to", "cc", "subject", "date", "attachment", "body")
    }
    return (
        "FOUNDER BRIEF (verbatim):\n"
        f"{brief_raw_text}\n\n"
        "EMAIL TO CLASSIFY:\n"
        f"{json.dumps(email_view, indent=2)}\n\n"
        "Return the JSON now."
    )


def classify_email(email: dict, brief_raw_text: str, model: str = llm_client.DEFAULT_MODEL) -> dict:
    prompt = build_prompt(email, brief_raw_text)
    return llm_client.complete_json(prompt, CLASSIFY_SYSTEM_PROMPT, model=model)
