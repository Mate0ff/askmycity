"""Runs data/eval_questions.md through the live agent as a correctness check.

Not part of `pytest`/CI — this makes real Anthropic API calls (costs money,
needs ANTHROPIC_API_KEY) and its output is a judgment call for a human to
skim, not a pass/fail assertion.

Usage:
    python scripts/run_eval.py                # all questions
    python scripts/run_eval.py --limit 5       # first 5 only (cheaper smoke run)
    python scripts/run_eval.py --out FILE.md   # default: data/eval_results.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from askmycity.agent import ask  # noqa: E402
from askmycity.data import load_dataset  # noqa: E402

QUESTION_LINE = re.compile(r"^\d+\.\s+(.*?)\s+—\s+(\S+)\s*$")


def parse_questions(path: Path) -> list[tuple[str, str]]:
    """Extracts (question, answer_type) pairs from eval_questions.md's
    numbered list, e.g. '1. How many...? — count'."""
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = QUESTION_LINE.match(line.strip())
        if m:
            questions.append((m.group(1), m.group(2)))
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default=str(REPO_ROOT / "data" / "eval_questions.md"))
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "eval_results.md"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    questions = parse_questions(Path(args.questions))
    if args.limit:
        questions = questions[: args.limit]
    print(f"Loaded {len(questions)} eval questions from {args.questions}")

    df = load_dataset()
    print(f"Dataset loaded: {len(df):,} rows")

    lines = ["# Eval results\n", f"Ran {len(questions)} questions from `eval_questions.md`.\n"]
    for i, (question, answer_type) in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question}")
        try:
            result = ask(question, df)
            tool_summary = "; ".join(
                f"{c.name}({c.input})" + (f" ERROR: {c.error}" if c.error else "")
                for c in result.tool_calls
            )
            lines.append(f"## {i}. {question}  _(expected: {answer_type})_\n")
            lines.append(f"**Answer:** {result.text}\n")
            lines.append(f"**Tool calls:** {tool_summary or '(none)'}\n")
        except Exception as exc:  # noqa: BLE001 - want to keep going and log the failure
            print(f"  ERROR: {exc}")
            lines.append(f"## {i}. {question}  _(expected: {answer_type})_\n")
            lines.append(f"**ERROR:** {exc}\n")

    out_path = Path(args.out)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
