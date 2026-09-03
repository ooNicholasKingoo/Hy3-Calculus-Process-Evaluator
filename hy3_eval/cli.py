from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .dataset import load_dataset, write_dataset, write_validation_cases
from .evaluator import run_benchmark
from .reporting import generate_report

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
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        if report.validation_results:
            csv_path = ROOT / "reports" / "validation_results.csv"
            rows = report.validation_results
            fieldnames = sorted({key for row in rows for key in row})
            with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    normalized = dict(row)
                    for key, value in normalized.items():
                        if isinstance(value, list):
                            normalized[key] = "、".join(str(item) for item in value)
                    writer.writerow(normalized)
        report_file = generate_report(ROOT)
        print(json.dumps({"total": report.total, "completed": report.completed,
                          "final_answer_accuracy": report.final_answer_accuracy,
                          "process_accuracy": report.process_accuracy,
                          "deterministic_error_rate": report.deterministic_error_rate,
                          "uncertain_process_rate": report.uncertain_process_rate,
                          "api_failures": report.api_failures,
                          "validation_total": report.validation_total,
                          "validation_first_error_detection_rate": report.validation_first_error_detection_rate,
                          "validation_first_error_localization_accuracy": report.validation_first_error_localization_accuracy,
                          "validation_false_positive_rate": report.validation_false_positive_rate,
                          "report": str(report_file)}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
