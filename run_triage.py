#!/usr/bin/env python3
"""Reusable email-triage pipeline entrypoint.

Usage:
    python run_triage.py --emails emails_raw.json --brief founder_brief.txt --out output

Nothing about the emails or brief content is hardcoded here or anywhere in
triage/ - point this at a different inbox and a different founder's brief
tomorrow and it runs the same way, provided the brief follows the same
header/bullet text convention.
"""
import argparse
import sys

from triage import pipeline, audit, briefing


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emails", required=True, help="Path to the raw emails JSON file")
    parser.add_argument("--brief", required=True, help="Path to the founder brief text file")
    parser.add_argument("--out", default="output", help="Output directory (default: output)")
    parser.add_argument("--model", default=None, help="LLM model to use (default: pipeline default)")
    parser.add_argument("--max-workers", type=int, default=6, help="Concurrent LLM calls (default: 6)")
    args = parser.parse_args()

    kwargs = {"max_workers": args.max_workers}
    if args.model:
        kwargs["model"] = args.model

    result = pipeline.run(args.emails, args.brief, **kwargs)
    audit.write_outputs(args.out, result["emails"], result["records"], result["drafts"])

    brief_md = briefing.generate_briefing(result["scenario"], result["emails"], result["records"], result["drafts"])
    with open(f"{args.out}/briefing_1130.md", "w", encoding="utf-8") as f:
        f.write(brief_md)

    print(f"Triaged {len(result['emails'])} emails -> {args.out}/", file=sys.stderr)
    print(brief_md)


if __name__ == "__main__":
    main()
