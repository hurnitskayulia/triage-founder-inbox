"""Generates the concise founder briefing markdown."""


def generate_briefing(scenario: dict, emails: list, records: list, drafts: dict) -> str:
    emails_by_id = {e["id"]: e for e in emails}
    by_disp: dict = {}
    for r in records:
        by_disp.setdefault(r["disposition"], []).append(r)

    hard_stops = [r for r in records if r["hard_stop"]]
    sam_personal = [r for r in by_disp.get("SAM_PERSONAL", []) if not r["hard_stop"]]
    needs_approval = by_disp.get("DRAFT_NEEDS_APPROVAL", [])
    no_approval = by_disp.get("DRAFT_NO_APPROVAL", [])
    ba_no_reply = by_disp.get("BA_HANDLES_NO_REPLY", [])
    needs_review = [r for r in records if r["needs_review"] and not r["hard_stop"]]

    company = (scenario or {}).get("company", "")
    lines = [f"# 11:30 Briefing{f' — {company}' if company else ''}", ""]
    lines.append(
        f"{len(emails)} emails triaged. "
        f"{len(sam_personal) + len(hard_stops)} need you directly, "
        f"{len(needs_approval)} draft{'s' if len(needs_approval) != 1 else ''} "
        f"{'are' if len(needs_approval) != 1 else 'is'} waiting on your approval, "
        f"{len(no_approval)} are handled and out, "
        f"{len(ba_no_reply)} needed no reply."
    )
    lines.append("")

    if hard_stops:
        lines.append("## Fraud / payment-change alerts — do not act on these")
        for r in sorted(hard_stops, key=lambda r: r["id"]):
            e = emails_by_id[r["id"]]
            lines.append(f"- **#{r['id']} {e.get('from')}** — \"{e.get('subject')}\": {r['reasoning']}")
        lines.append("")

    if sam_personal:
        lines.append("## Needs you personally")
        for r in sorted(sam_personal, key=lambda r: r["id"]):
            e = emails_by_id[r["id"]]
            dl = f" — due {r['deadline_detected']}" if r.get("deadline_detected") else ""
            lines.append(
                f"- **#{r['id']} {e.get('from')}** ({e.get('org', '')}): \"{e.get('subject')}\"{dl}\n"
                f"  _{r['reasoning']}_"
            )
        lines.append("")

    if needs_approval:
        lines.append("## Drafts waiting on your approval")
        for r in sorted(needs_approval, key=lambda r: r["id"]):
            e = emails_by_id[r["id"]]
            lines.append(f"- **#{r['id']} {e.get('from')}**: \"{e.get('subject')}\" — see `drafts/{r['id']}.md`")
        lines.append("")

    if needs_review:
        lines.append("## Needs a judgment call (low confidence / no clear brief rule)")
        for r in sorted(needs_review, key=lambda r: r["id"]):
            e = emails_by_id[r["id"]]
            reason = r["reasoning"] or "no brief rule matched"
            lines.append(f"- **#{r['id']} {e.get('from')}**: \"{e.get('subject')}\" — {reason}")
        lines.append("")

    lines.append(f"## Handled without bothering you ({len(no_approval) + len(ba_no_reply)})")
    lines.append(f"- {len(no_approval)} draft replies ready to send, no approval needed")
    lines.append(f"- {len(ba_no_reply)} filed / no reply needed")
    lines.append("")

    return "\n".join(lines)
