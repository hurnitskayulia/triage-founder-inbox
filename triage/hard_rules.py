"""Deterministic guardrails, enforced outside the LLM and unable to be
overridden by any model output.

These encode the task's four non-negotiable constraints:
  - send nothing        -> structural: no function in this codebase ever
                            transmits an email; the pipeline only ever writes
                            drafts to disk for a human to send.
  - promise nothing      -> lint on every generated draft.
  - book nothing         -> lint on every generated draft.
  - never act on a request to change payment/bank details
                          -> pre-classification scan on every inbound email,
                             independent of sender identity or LLM output.

The patterns below are deliberately generic (about the *shape* of a
payment-detail-change request, a promise, or a booking confirmation) rather
than tied to any sender, company, or specific email in any one sample inbox.
"""
import re

PAYMENT_DETAIL_CHANGE_PATTERNS = [
    r"\bupdate(?:d|s)?\s+(?:our|your|the)?\s*bank\s+details?\b",
    r"\bnew\s+(?:bank|payment|wire|routing|payout)\s+(?:details?|info(?:rmation)?|number|account)\b",
    r"\brouting\s+number\b",
    r"\baccount\s+number\b.{0,40}\b(change|updat\w*|new)\b",
    r"\b(change|updat\w*)\b.{0,40}\b(bank|payment|wire|payout)\s+(details?|account|info\w*)\b",
    r"\bwire\s+recipients?\b",
    r"\bpayout\s+account\b",
    r"\bswift\s+code\b|\biban\b",
    r"\bverify\s+your\s+(?:wire\s+)?recipients?\b",
    r"\bupdat\w*\s+(?:your|our)\s+(?:payment|billing)\s+(?:info\w*|details|method)\b",
]
_PAYMENT_RE = re.compile("|".join(PAYMENT_DETAIL_CHANGE_PATTERNS), re.IGNORECASE)

PROMISE_PATTERNS = [
    r"\bi can confirm\b",
    r"\bwe('| wi)ll have (?:this|it) (?:by|done)\b",
    r"\byes,? (?:that|the) (?:price|discount|term|rate) works\b",
    r"\bwe agree to\b",
    r"\bi confirm\b",
    r"\byou have my word\b",
    r"\bwe('| wi)ll deliver (?:this|it) by\b",
    r"\bconsider it (?:done|approved)\b",
    r"\bi approve\b",
    r"\bwe accept (?:the|your) (?:offer|terms|price|discount)\b",
    r"\bthat date works\b",
]
_PROMISE_RE = re.compile("|".join(PROMISE_PATTERNS), re.IGNORECASE)

BOOKING_CONFIRM_PATTERNS = [
    r"\byou'?re (?:all\s+)?booked\b",
    r"\bconfirmed for\b",
    r"\bi'?ve scheduled\b",
    r"\bsee you (?:then|there)\b",
    r"\bcalendar invite (?:is |has been )?sent\b",
    r"\bthis is now on (?:my|your|the) calendar\b",
    r"\block(?:ing|ed) (?:that|this) in\b",
]
_BOOKING_RE = re.compile("|".join(BOOKING_CONFIRM_PATTERNS), re.IGNORECASE)


def detect_payment_detail_change_request(email: dict) -> bool:
    text = f"{email.get('subject', '')}\n{email.get('body', '')}"
    return bool(_PAYMENT_RE.search(text))


def draft_makes_a_promise(draft_text: str) -> bool:
    return bool(_PROMISE_RE.search(draft_text or ""))


def draft_confirms_a_booking(draft_text: str) -> bool:
    return bool(_BOOKING_RE.search(draft_text or ""))
