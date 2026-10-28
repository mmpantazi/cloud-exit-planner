# Cloud Exit Planner

Point it at a repo. It reads your Terraform, Dockerfiles, compose files, `.env` files and dependency lists, lists the vendor services you depend on, estimates what leaving costs, and prints an EU Data Act-style migration checklist with dates. It works offline, uses only the Python standard library (3.11+), and never prints secret values.

RO: estimează costurile și pașii pentru a pleca de la un furnizor cloud; `--lang ro` traduce lista de pași și titlurile.

## Run

```bash
python -m cloudexit PATH [--size storage=2000 --size database=150] [--monthly-bill 1200] [--commitment 3000]
python -m cloudexit examples/demo --size storage=2000 --size database=150 --monthly-bill 1200
python -m cloudexit PATH --lang ro -o plan.md
python -m cloudexit PATH --format json
```

Or `pip install .` and run `cloudexit PATH`.

| Option | Meaning |
|---|---|
| `--size NAME=GB` | Data to move. `NAME` is a category (`storage`, `database`) or a service key such as `aws_s3` (the key wins). Repeatable. Without it the report shows the cost per TB instead of guessing. |
| `--monthly-bill EUR`, `--parallel-months N` | Cost of running the old environment while you switch (default 1 month). |
| `--commitment EUR` | Remaining committed spend or early-termination fee. These are not covered by the Data Act ban, so they are listed separately. |
| `--day-rate EUR` | Engineering cost per day (default 400). |
| `--notice-date YYYY-MM-DD` | When you plan to send the switching request (default today). |
| `--fx` | USD to EUR for egress prices (default 0.92). |
| `--lang en\|ro`, `--format md\|json`, `-o FILE` | Output controls. |

## What it reports

1. **Services in use** with a lock-in level (portable / moderate / proprietary), where each was found, and a 0-100 lock-in score.
2. **Egress** under three regimes: list price, the provider's leave-waiver (AWS, Azure, Google Cloud), and after 12 January 2027 when the Data Act bans switching charges for the one-off move (parallel-use traffic can still be charged at cost).
3. **Cost picture**: egress range, engineering effort range, parallel running, commitments.
4. **Timing**: notice (max two months), 30-day transition, 30-day retrieval period, and the earliest notice date that makes the switch start on or after 12 January 2027.
5. **Things that make exit harder**: archive storage classes, customer-managed KMS keys, multi-AZ databases.
6. **Checklist** in six phases plus service-specific porting steps and EU-friendly target ideas.

## What it recognises

- Terraform `.tf` resources for AWS, Azure and Google (comments ignored, `count` honoured) and `.tfstate` (resource types only).
- `Dockerfile*` `FROM` and `ENV`, compose `image:` and environment entries, `.env*` files: provider key names and endpoint hosts (RDS, S3, Blob, Cloud SQL, ...).
- `requirements*.txt` and `package.json` SDK dependencies (boto3, `@azure/*`, `@google-cloud/*`, firebase).

Skipped folders: `.git`, `node_modules`, `.terraform`, virtualenvs, `vendor`, `dist`, `build`.

## Limits

- Prices are indicative list prices (`cloudexit/pricing.py`, as of 2026-10). Confirm them on the provider's page. Waiver terms (such as the 60-day limit) come from press coverage of the vendors' announcements.
- Article numbers come from law-firm commentary on Regulation (EU) 2023/2854, not from the EUR-Lex text. This is planning help, not legal advice.
- Engineering days are a coarse model (0.5 / 2 / 5 days per portable / moderate / proprietary service). Treat the range as a prompt for your own estimate.
- Service steps in the Romanian report stay in English.
- Data volume is never guessed; you must provide it.

## Test

```bash
python -m unittest discover -s tests
```
