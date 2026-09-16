"""Streamlit front end for the founder-inbox triage pipeline.

This file is purely a thin UI wrapper: it uploads files, calls the existing
triage pipeline exactly as run_triage.py does, and displays/downloads the
results. It contains no classification, routing, hard-rule, or drafting
logic of its own - all of that lives in triage/*.py and is untouched here.

Run with: streamlit run streamlit_app.py
"""
import io
import os
import tempfile
import zipfile
from collections import Counter

import streamlit as st

from triage import audit, briefing, llm_client, pipeline

st.set_page_config(page_title="Founder Inbox Triage", page_icon="📥", layout="wide")

st.title("Founder Inbox Triage")
st.caption(
    "Upload a raw inbox export and a founder preferences brief, then run the triage "
    "pipeline. The system only classifies emails and drafts replies for review - it "
    "never sends anything, books anything, pays anything, or acts on a request to "
    "change payment or bank details."
)

with st.sidebar:
    st.header("Options")
    model = st.text_input(
        "LLM model", value=llm_client.DEFAULT_MODEL,
        help="Passed to the `claude` CLI for classification and draft generation.",
    )
    max_workers = st.slider("Concurrent LLM calls", min_value=1, max_value=12, value=6)
    st.caption(
        "Requires the `claude` CLI to be installed and logged in on this machine - "
        "that's what actually talks to the model, this app just orchestrates it."
    )

col1, col2 = st.columns(2)
with col1:
    emails_file = st.file_uploader("emails_raw.json", type=["json"])
with col2:
    brief_file = st.file_uploader("founder_brief.txt", type=["txt"])

run_clicked = st.button("Run Triage", type="primary", disabled=not (emails_file and brief_file))

if run_clicked:
    work_dir = tempfile.mkdtemp(prefix="triage_run_")
    emails_path = os.path.join(work_dir, "emails_raw.json")
    brief_path = os.path.join(work_dir, "founder_brief.txt")
    with open(emails_path, "wb") as f:
        f.write(emails_file.getvalue())
    with open(brief_path, "wb") as f:
        f.write(brief_file.getvalue())

    out_dir = os.path.join(work_dir, "output")

    with st.spinner(
        f"Classifying emails and drafting replies via {model} - "
        "this can take a couple of minutes for a full inbox..."
    ):
        try:
            result = pipeline.run(emails_path, brief_path, model=model, max_workers=max_workers)
        except Exception as e:
            st.error(f"Triage run failed: {e}")
            st.stop()

        audit.write_outputs(out_dir, result["emails"], result["records"], result["drafts"])
        brief_md = briefing.generate_briefing(
            result["scenario"], result["emails"], result["records"], result["drafts"]
        )
        with open(os.path.join(out_dir, "briefing_1130.md"), "w", encoding="utf-8") as f:
            f.write(brief_md)

    st.session_state["out_dir"] = out_dir
    st.session_state["records"] = result["records"]
    st.session_state["briefing_md"] = brief_md
    st.session_state["drafts"] = result["drafts"]
    st.success(f"Triaged {len(result['emails'])} emails.")

if "records" not in st.session_state:
    st.info("Upload both files and click **Run Triage** to get started.")
    st.stop()

records = st.session_state["records"]
out_dir = st.session_state["out_dir"]
brief_md = st.session_state["briefing_md"]
drafts = st.session_state["drafts"]

st.header("Disposition counts")
counts = Counter(r["disposition"] for r in records)
metric_cols = st.columns(4)
for col, (key, label) in zip(
    metric_cols,
    [
        ("SAM_PERSONAL", "Needs Sam personally"),
        ("DRAFT_NEEDS_APPROVAL", "Drafts needing approval"),
        ("DRAFT_NO_APPROVAL", "Drafts, no approval needed"),
        ("BA_HANDLES_NO_REPLY", "Handled, no reply needed"),
    ],
):
    col.metric(label, counts.get(key, 0))
st.caption(
    f"{len(records)} emails total · "
    f"{sum(1 for r in records if r['needs_review'])} flagged for review · "
    f"{sum(1 for r in records if r['hard_stop'])} hard-stopped (fraud / payment-change)"
)

st.header("11:30 Founder Briefing")
st.markdown(brief_md)

st.header("Flagged for review")
flagged = sorted((r for r in records if r["needs_review"]), key=lambda r: r["id"])
if flagged:
    st.dataframe(
        [
            {
                "ID": r["id"],
                "Owner": r["owner"],
                "Disposition": r["disposition"],
                "Confidence": r["confidence"],
                "Matched rule": r["matched_rule"],
                "Reasoning": r["reasoning"],
            }
            for r in flagged
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.write("Nothing flagged for review in this run.")

st.header("Draft replies")
if drafts:
    for rid in sorted(drafts):
        rec = next(r for r in records if r["id"] == rid)
        with st.expander(f"#{rid} - {rec['disposition']}"):
            path = os.path.join(out_dir, "drafts", f"{rid}.md")
            with open(path, encoding="utf-8") as f:
                draft_text = f.read()
            st.markdown(draft_text)
            st.download_button(
                "Download this draft", draft_text.encode("utf-8"),
                file_name=f"{rid}.md", mime="text/markdown", key=f"draft-{rid}",
            )
else:
    st.write("No draft replies were generated in this run.")

st.header("Downloads")


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


d1, d2, d3, d4, d5 = st.columns(5)
d1.download_button(
    "classified_emails.json", _read(os.path.join(out_dir, "classified_emails.json")),
    file_name="classified_emails.json", mime="application/json",
)
d2.download_button(
    "audit_log.csv", _read(os.path.join(out_dir, "audit_log.csv")),
    file_name="audit_log.csv", mime="text/csv",
)
d3.download_button(
    "flagged_for_review.json", _read(os.path.join(out_dir, "flagged_for_review.json")),
    file_name="flagged_for_review.json", mime="application/json",
)
d4.download_button(
    "briefing_1130.md", brief_md.encode("utf-8"),
    file_name="briefing_1130.md", mime="text/markdown",
)

zip_buf = io.BytesIO()
drafts_dir = os.path.join(out_dir, "drafts")
with zipfile.ZipFile(zip_buf, "w") as zf:
    for name in sorted(os.listdir(drafts_dir)):
        zf.write(os.path.join(drafts_dir, name), arcname=name)
d5.download_button(
    "drafts.zip", zip_buf.getvalue(), file_name="drafts.zip", mime="application/zip",
    disabled=not drafts,
)
