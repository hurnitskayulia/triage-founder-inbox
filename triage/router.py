"""Deterministic decision layer.

Takes the LLM's classification plus the hard-rule scan and produces the
final, auditable disposition. This is the only place allowed to decide
owner/approval when the LLM's output is missing, malformed, low-confidence,
or in conflict with a hard-rule guardrail. Every override is recorded, so
the audit trail shows exactly where the model's judgment was trusted versus
overruled.
"""
from . import hard_rules

VALID_OWNERS = {"SAM", "BA"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def _validate_llm_output(llm_out: dict):
    notes = []
    out = dict(llm_out) if isinstance(llm_out, dict) else {}

    if out.get("owner") not in VALID_OWNERS:
        notes.append(f"invalid/missing owner {out.get('owner')!r}; defaulted to SAM")
        out["owner"] = "SAM"
    if not isinstance(out.get("needs_reply"), bool):
        notes.append("invalid/missing needs_reply; defaulted to False")
        out["needs_reply"] = False
    if not isinstance(out.get("llm_suggested_needs_sam_approval"), bool):
        out["llm_suggested_needs_sam_approval"] = True
    if out.get("confidence") not in VALID_CONFIDENCE:
        notes.append(f"invalid/missing confidence {out.get('confidence')!r}; defaulted to low")
        out["confidence"] = "low"
    if not out.get("matched_rule"):
        notes.append("no matched_rule provided")
        out["matched_rule"] = "NO_MATCHING_RULE"
    out.setdefault("reasoning", "")
    out.setdefault("topic_tags", [])
    out.setdefault("vip", False)
    out.setdefault("deadline_detected", None)
    return out, notes


def _disposition(owner: str, needs_reply: bool, needs_sam_approval: bool) -> str:
    if owner == "SAM":
        return "SAM_PERSONAL"
    if not needs_reply:
        return "BA_HANDLES_NO_REPLY"
    return "DRAFT_NEEDS_APPROVAL" if needs_sam_approval else "DRAFT_NO_APPROVAL"


def resolve(email: dict, llm_out: dict) -> dict:
    sanitized, overrides = _validate_llm_output(llm_out)

    owner = sanitized["owner"]
    needs_reply = sanitized["needs_reply"]
    confidence = sanitized["confidence"]
    matched_rule = sanitized["matched_rule"]
    needs_sam_approval = sanitized["llm_suggested_needs_sam_approval"]

    # Uncertainty always escalates up, never resolves toward autonomous action.
    if matched_rule == "NO_MATCHING_RULE" or confidence == "low":
        if owner != "SAM":
            overrides.append("uncertain classification (no matched rule / low confidence); escalated owner to SAM")
        owner = "SAM"
        needs_review = True
    else:
        needs_review = False

    hard_stop = hard_rules.detect_payment_detail_change_request(email)
    if hard_stop:
        if owner != "SAM" or needs_reply:
            overrides.append(
                "hard-rule guardrail: request to change payment/bank details detected; "
                "forced to Sam, no BA draft generated"
            )
        owner = "SAM"
        needs_reply = False
        needs_review = True

    disposition = _disposition(owner, needs_reply, needs_sam_approval)

    return {
        "id": email["id"],
        "owner": owner,
        "needs_reply": needs_reply,
        "needs_sam_approval": needs_sam_approval,
        "disposition": disposition,
        "hard_stop": hard_stop,
        "hard_stop_reason": "payment/bank detail change request detected" if hard_stop else None,
        "needs_review": needs_review,
        "topic_tags": sanitized["topic_tags"],
        "matched_rule": matched_rule,
        "reasoning": sanitized["reasoning"],
        "confidence": confidence,
        "vip": sanitized["vip"],
        "deadline_detected": sanitized["deadline_detected"],
        "overrides_applied": overrides,
        "llm_raw": llm_out,
    }
