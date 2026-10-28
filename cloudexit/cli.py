import argparse
import os
import sys
from datetime import date

from .checklist import LANGS
from .letter import drafts
from .estimate import make_plan, parse_date
from .report import to_json, to_markdown
from .scanner import scan


def parse_sizes(items):
    sizes = {}
    for item in items or []:
        key, sep, val = item.partition("=")
        try:
            gb = float(val)
        except ValueError:
            gb = -1
        if not sep or gb < 0:
            raise SystemExit(f"--size expects NAME=GB (for example storage=500), got '{item}'")
        sizes[key.strip().lower()] = gb
    return sizes


def build_parser():
    p = argparse.ArgumentParser(prog="cloudexit", description="Plan an exit from a cloud vendor from your Terraform, Docker, compose and env files.")
    p.add_argument("path", nargs="?", default=".", help="folder or file to scan (default: .)")
    p.add_argument("--size", action="append", metavar="NAME=GB", help="data to move: category (storage, database) or service key (aws_s3), in GB; repeatable")
    p.add_argument("--monthly-bill", type=float, default=0.0, metavar="EUR", help="current monthly cloud bill, for the parallel-run cost")
    p.add_argument("--parallel-months", type=float, default=1.0, help="months both environments run (default 1)")
    p.add_argument("--commitment", type=float, default=0.0, metavar="EUR", help="remaining committed spend or early-termination fee")
    p.add_argument("--day-rate", type=float, default=400.0, metavar="EUR", help="engineering cost per day (default 400)")
    p.add_argument("--fx", type=float, default=0.92, help="USD to EUR rate for egress prices (default 0.92)")
    p.add_argument("--notice-date", metavar="YYYY-MM-DD", help="day you plan to send the switching request (default: today)")
    p.add_argument("--today", metavar="YYYY-MM-DD", help=argparse.SUPPRESS)
    p.add_argument("--lang", choices=LANGS, default="en", help="report language (en, ro)")
    p.add_argument("--format", choices=("md", "json"), default="md")
    p.add_argument("--letter", action="store_true", help="print a draft switching-request letter per provider instead of the report")
    p.add_argument("-o", "--output", help="write the report to this file instead of stdout")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        today = parse_date(args.today) if args.today else date.today()
        notice = parse_date(args.notice_date) if args.notice_date else today
    except ValueError:
        raise SystemExit("dates must look like 2026-12-01")
    sizes = parse_sizes(args.size)
    if not os.path.exists(args.path):
        raise SystemExit(f"path not found: {args.path}")
    result = scan(args.path)
    plan = make_plan(result, sizes, args.monthly_bill, args.parallel_months, args.commitment, args.day_rate, notice)
    if args.letter:
        if not plan.services:
            raise SystemExit("no provider services found, nothing to write a letter about")
        text = drafts(plan, notice, args.lang)
    elif args.format == "json":
        text = to_json(result, plan, args.fx)
    else:
        text = to_markdown(result, plan, args.lang, args.fx)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
