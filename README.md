# Founder Inbox Triage

Classifies a founder's inbox against a written preferences brief, drafts
replies where appropriate, and produces an auditable, downloadable report.
The system only classifies and drafts - it never sends email, books
anything, pays anything, or acts on a request to change payment or bank
details.

## Prerequisites

- Python 3.10+
- The [Claude Code CLI](https://claude.com/claude-code) (`claude`) installed
  and logged in on this machine. The pipeline shells out to `claude -p` as
  its LLM backend, so this app needs no separate API key - just a working,
  authenticated `claude` command on your `PATH`. Check with:

  ```
  claude --version
  ```

## Install

```
pip install -r requirements.txt
```

## Run the web interface

```
streamlit run streamlit_app.py
```

This opens the app in your browser (usually `http://localhost:8501`). Then:

1. Upload your `emails_raw.json` file.
2. Upload your `founder_brief.txt` file.
3. Click **Run Triage**.
4. Once it finishes (a full 50-email inbox takes a couple of minutes), review:
   - Disposition counts
   - The 11:30 founder briefing
   - The flagged-for-review items
   - Each generated draft reply
5. Download `classified_emails.json`, `audit_log.csv`,
   `flagged_for_review.json`, `briefing_1130.md`, and `drafts.zip` from the
   Downloads section.

The model and concurrency used for the LLM calls can be adjusted in the
sidebar; sensible defaults are pre-filled.

## Run from the command line instead

The original CLI pipeline still works on its own and is unaffected by the
web interface:

```
python run_triage.py --emails emails_raw.json --brief founder_brief.txt --out output
```

## Applying manual corrections

After reviewing the output, human-reviewed corrections can be layered on
top without re-running the LLM or hand-editing generated files:

```
python apply_corrections.py --corrections output/manual_corrections.json
```

This re-applies `output/manual_corrections.json` and regenerates every
dependent file (`classified_emails.json`, `audit_log.csv`,
`flagged_for_review.json`, `briefing_1130.md`) so nothing drifts out of
sync. It is idempotent - safe to re-run after adding new entries to the
corrections file.

## Project structure

```
triage/                  Core pipeline (untouched by the web interface)
  loader.py               Reads emails_raw.json / founder_brief.txt
  brief_parser.py          Parses the brief into sections
  hard_rules.py             Deterministic guardrails (payment-detail-change
                             detection, promise/booking lints)
  llm_client.py              LLM backend (shells out to `claude -p`)
  classifier.py                LLM-based email classification
  router.py                     Validates/overrides LLM output, applies
                                 hard rules, resolves final disposition
  draft_generator.py             Drafts replies + lints them
  corrections.py                  Applies manual correction overrides
  audit.py                         Writes output files
  briefing.py                       Generates the founder briefing
run_triage.py             CLI entrypoint
apply_corrections.py      Applies a manual-corrections file to existing output
streamlit_app.py          Web interface (this file's counterpart)
requirements.txt          Python dependencies for the web interface
```
