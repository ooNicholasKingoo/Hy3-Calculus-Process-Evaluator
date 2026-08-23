from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import load_dataset, write_dataset, write_validation_cases
from .evaluator import run_benchmark

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "problems.jsonl"

def main() -> None:
    parser = argparse.ArgumentParser(description="Hy3 calculus evaluator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-dataset")
    bench = sub.add_parser("benchmark")
    bench.add_argument("--offline", action="store_true")
    bench.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.command == "validate-dataset":
        problems = write_dataset(DATA)
        write_validation_cases(ROOT / "data" / "validation_cases.jsonl", problems)
        print(f"dataset valid: {len(problems)} problems -> {DATA}")
    elif args.command == "benchmark":
        if not DATA.exists(): write_dataset(DATA)
        report = run_benchmark(load_dataset(DATA), offline=args.offline, limit=args.limit)
        out = ROOT / "reports" / "latest_benchmark.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"total": report.total, "completed": report.completed,
                          "final_answer_accuracy": report.final_answer_accuracy,
                          "process_accuracy": report.process_accuracy,
                          "deterministic_error_rate": report.deterministic_error_rate,
                          "uncertain_process_rate": report.uncertain_process_rate,
                          "api_failures": report.api_failures}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
