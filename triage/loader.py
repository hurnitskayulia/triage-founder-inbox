"""Loads the two reusable inputs: a raw emails file and a founder brief.

Makes no assumptions specific to any one inbox or company. The emails file
may be a plain JSON list of emails, or a dict with an "emails" key (optionally
alongside "scenario" / "calendar" context, which are used opportunistically
if present and simply ignored if not).
"""
import json


def load_emails(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data, None, None

    if isinstance(data, dict):
        emails = data.get("emails")
        if emails is None:
            raise ValueError(f"{path}: expected a list of emails, or a dict with an 'emails' key")
        return emails, data.get("scenario"), data.get("calendar")

    raise ValueError(f"{path}: unrecognized structure for an emails file")


def format_calendar_context(calendar: dict) -> str:
    lines = [f"Timezone: {calendar.get('timezone', '')}", f"Week of: {calendar.get('week_of', '')}"]
    for day in calendar.get("events", []):
        lines.append(f"{day.get('day')}:")
        for item in day.get("items", []):
            lines.append(f"  - {item}")
    return "\n".join(lines)
