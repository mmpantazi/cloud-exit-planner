import json
import os
import tempfile
import unittest
from datetime import date

from cloudexit.cli import main, parse_sizes
from cloudexit.estimate import add_months, build_timeline, make_plan
from cloudexit.pricing import list_price
from cloudexit.report import to_json, to_markdown
from cloudexit.scanner import scan

DEMO = os.path.join(os.path.dirname(__file__), "..", "examples", "demo")


def project(files):
    d = tempfile.mkdtemp()
    for name, text in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
    return d


class ScannerTests(unittest.TestCase):
    def test_terraform_resources_and_count(self):
        d = project({"a.tf": 'resource "aws_instance" "w" {\n count = 3\n}\nresource "aws_s3_bucket" "b" {}\n'})
        r = scan(d)
        self.assertEqual(r.findings["aws_ec2"].resources, 3)
        self.assertEqual(r.findings["aws_s3"].resources, 1)
        self.assertEqual(r.providers, {"aws"})

    def test_commented_resources_ignored(self):
        d = project({"a.tf": '# resource "aws_s3_bucket" "x" {}\n/* resource "aws_db_instance" "y" {} */\n'})
        self.assertEqual(scan(d).findings, {})

    def test_networking_is_not_a_service(self):
        r = scan(project({"n.tf": 'resource "aws_vpc" "v" {}\nresource "aws_subnet" "s" {}\n'}))
        self.assertEqual(r.findings, {})
        self.assertEqual(r.infra_only["aws_vpc"], 1)

    def test_other_providers_not_matched(self):
        r = scan(project({"a.tf": 'resource "cloudflare_record" "r" {}\nresource "hcloud_server" "s" {}\n'}))
        self.assertEqual(r.providers, set())

    def test_compose_images(self):
        d = project({"docker-compose.yml": "services:\n  a:\n    image: gcr.io/p/app:1\n  b:\n    image: postgres:16\n"})
        r = scan(d)
        self.assertIn("gcp_gke_vm", r.findings)
        self.assertEqual(r.portable_images, {"postgres"})

    def test_secrets_never_stored(self):
        d = project({".env": "DATABASE_URL=postgres://u:hunter2@x.rds.amazonaws.com/db\nAWS_SECRET_ACCESS_KEY=AKIAHUNTER2\n"})
        r = scan(d)
        dump = json.dumps([e.__dict__ for f in r.findings.values() for e in f.evidence])
        self.assertNotIn("hunter2", dump)
        self.assertNotIn("AKIAHUNTER2", dump)
        self.assertIn("aws_rds", r.findings)

    def test_dockerfile_from_and_env(self):
        d = project({"Dockerfile": "FROM public.ecr.aws/lambda/python:3.12\nENV AZURE_STORAGE_ACCOUNT acct\n"})
        r = scan(d)
        self.assertEqual(r.providers, {"aws", "azure"})

    def test_sdk_dependencies(self):
        d = project({"requirements.txt": "boto3==1.0\nazure-storage-blob>=12\nrequests\n",
                     "web/package.json": json.dumps({"dependencies": {"@google-cloud/storage": "^7", "express": "4"}})})
        r = scan(d)
        self.assertEqual(r.providers, {"aws", "azure", "gcp"})
        self.assertIn("gcp_gcs", r.findings)

    def test_tfstate_types_only(self):
        state = {"resources": [{"mode": "managed", "type": "aws_dynamodb_table", "name": "t", "instances": [{}, {}]}]}
        r = scan(project({"terraform.tfstate": json.dumps(state)}))
        self.assertEqual(r.findings["aws_dynamodb"].resources, 2)

    def test_skip_dirs(self):
        d = project({"node_modules/x/main.tf": 'resource "aws_s3_bucket" "b" {}\n'})
        self.assertEqual(scan(d).findings, {})

    def test_archive_risk(self):
        r = scan(project({"a.tf": 'resource "aws_s3_bucket" "b" {\n storage_class = "DEEP_ARCHIVE"\n}\n'}))
        self.assertEqual(len(r.risks), 1)


class PricingTests(unittest.TestCase):
    def test_free_allowance(self):
        self.assertEqual(list_price("aws", 100), 0)

    def test_tiers(self):
        self.assertAlmostEqual(list_price("aws", 10_340), 10_240 * 0.09)
        self.assertAlmostEqual(list_price("aws", 10_340 + 1000), 10_240 * 0.09 + 1000 * 0.085)

    def test_gcp_no_free(self):
        self.assertAlmostEqual(list_price("gcp", 100), 12.0)


class EstimateTests(unittest.TestCase):
    def test_add_months_clamps(self):
        self.assertEqual(add_months(date(2026, 12, 31), 2), date(2027, 2, 28))

    def test_timeline_ban_date(self):
        early = build_timeline(date(2026, 10, 28))
        self.assertFalse(early.start_after_ban)
        self.assertEqual(early.earliest_notice_for_ban, date(2026, 11, 12))
        self.assertTrue(build_timeline(date(2026, 11, 12)).start_after_ban)
        self.assertEqual((early.retrieval_end - early.latest_start).days, 60)

    def test_sizes_split_evenly_and_key_overrides(self):
        r = scan(project({"a.tf": 'resource "aws_s3_bucket" "b" {}\nresource "aws_db_instance" "d" {}\n'}))
        plan = make_plan(r, {"storage": 1000, "database": 200})
        self.assertEqual(plan.egress[0].gb, 1200)
        plan = make_plan(r, {"aws_s3": 500, "storage": 1000})
        self.assertEqual(plan.egress[0].gb, 500)

    def test_lockin_score_bounds(self):
        low = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {}\n'})))
        high = make_plan(scan(project({"a.tf": 'resource "aws_lambda_function" "i" {}\n'})))
        self.assertEqual((low.lockin_score, high.lockin_score), (0, 100))

    def test_effort_grows_with_resources(self):
        one = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {}\n'})))
        many = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {\n count = 5\n}\n'})))
        self.assertGreater(many.effort_days[1], one.effort_days[1])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.result = scan(DEMO)
        self.plan = make_plan(self.result, {"storage": 2000}, monthly_bill=1000, notice=date(2026, 10, 28))

    def test_markdown_sections(self):
        md = to_markdown(self.result, self.plan)
        for part in ("Services in use", "Cost picture", "Timing", "Migration checklist", "Amazon S3", "2026-11-12"):
            self.assertIn(part, md)

    def test_unsized_report_shows_per_tb(self):
        md = to_markdown(self.result, make_plan(self.result))
        self.assertIn("No data sizes were given", md)

    def test_romanian(self):
        md = to_markdown(self.result, self.plan, "ro")
        self.assertIn("Plan de ieșire din cloud", md)
        self.assertIn("Cererea de schimbare", md)

    def test_json_roundtrip(self):
        data = json.loads(to_json(self.result, self.plan))
        self.assertEqual(data["providers"], ["aws"])
        self.assertTrue(data["services"])

    def test_empty_project(self):
        r = scan(project({"README.md": "hi"}))
        md = to_markdown(r, make_plan(r))
        self.assertIn("No vendor-specific services", md)


class CliTests(unittest.TestCase):
    def test_bad_size(self):
        with self.assertRaises(SystemExit):
            parse_sizes(["storage"])
        with self.assertRaises(SystemExit):
            parse_sizes(["storage=abc"])

    def test_output_file(self):
        out = os.path.join(tempfile.mkdtemp(), "plan.md")
        self.assertEqual(main([DEMO, "-o", out, "--today", "2026-10-28"]), 0)
        with open(out) as fh:
            self.assertIn("Cloud Exit Plan", fh.read())

    def test_missing_path(self):
        with self.assertRaises(SystemExit):
            main(["/nonexistent/dir"])


if __name__ == "__main__":
    unittest.main()
