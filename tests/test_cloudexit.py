import json
import os
import tempfile
import unittest
from datetime import date

from cloudexit.cli import main, parse_sizes
from cloudexit.estimate import add_months, build_timeline, make_plan, transfer_hours
from cloudexit.letter import drafts
from cloudexit import pricing
from cloudexit.pricing import list_price
from cloudexit.report import to_json, to_markdown, totals
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


class TemplateScannerTests(unittest.TestCase):
    def test_cloudformation(self):
        r = scan(project({"cfn.yaml": "Resources:\n  B:\n    Type: AWS::S3::Bucket\n  V:\n    Type: AWS::EC2::VPC\n"}))
        self.assertEqual(set(r.findings), {"aws_s3"})
        self.assertIn("aws", r.providers)

    def test_bicep_and_networking(self):
        r = scan(project({"main.bicep": "resource a 'Microsoft.Storage/storageAccounts@2023-01-01' = {}\nresource n 'Microsoft.Network/virtualNetworks@2023-01-01' = {}\n"}))
        self.assertEqual(set(r.findings), {"az_blob"})

    def test_kubernetes_annotations(self):
        r = scan(project({"k/sc.yaml": "provisioner: ebs.csi.aws.com\nmetadata:\n  annotations:\n    eks.amazonaws.com/role-arn: arn:x\n"}))
        self.assertEqual(set(r.findings), {"aws_ebs", "aws_iam_cognito"})

    def test_serverless_framework(self):
        r = scan(project({"serverless.yml": "service: x\nprovider:\n  name: aws\n  runtime: nodejs20.x\n"}))
        self.assertIn("aws_lambda", r.findings)

    def test_serverless_other_provider_ignored(self):
        r = scan(project({"serverless.yml": "provider:\n  name: azure\n"}))
        self.assertEqual(r.findings, {})

    def test_plain_yaml_ignored(self):
        self.assertEqual(scan(project({"ci.yml": "name: build\non: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n"})).findings, {})


class ModuleTests(unittest.TestCase):
    def test_registry_modules(self):
        tf = """
module "bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "4.0"
}
module "db" { source = "terraform-aws-modules/rds/aws" }
module "net" { source = "terraform-aws-modules/vpc/aws" }
module "aks" { source = "Azure/aks/azurerm" }
module "gcs" { source = "terraform-google-modules/cloud-storage/google" }
module "local" { source = "./modules/thing" }
"""
        r = scan(project({"m.tf": tf}))
        self.assertEqual(set(r.findings), {"aws_s3", "aws_rds", "az_aks_vm", "gcp_gcs"})
        self.assertEqual(r.providers, {"aws", "azure", "gcp"})


class PricingTests(unittest.TestCase):
    def tearDown(self):
        pricing.TIERS["aws"] = [(10_240, 0.09), (51_200, 0.085), (153_600, 0.07), (None, 0.05)]
        pricing.FREE_GB["aws"] = 100

    def test_override(self):
        pricing.apply_overrides({"aws": {"free_gb": 0, "tiers": [[None, 0.02]]}})
        self.assertAlmostEqual(list_price("aws", 1000), 20.0)

    def test_override_validation(self):
        with self.assertRaises(ValueError):
            pricing.apply_overrides({"oracle": {}})
        with self.assertRaises(ValueError):
            pricing.apply_overrides({"aws": {"tiers": [[100, 0.1]]}})
        with self.assertRaises(ValueError):
            pricing.apply_overrides({"aws": {"tiers": [[500, 0.1], [100, 0.09], [None, 0.05]]}})

    def test_cli_prices_file_errors(self):
        bad = os.path.join(tempfile.mkdtemp(), "p.json")
        with open(bad, "w") as fh:
            fh.write("{not json")
        with self.assertRaises(SystemExit):
            main([DEMO, "--prices", bad])
        with self.assertRaises(SystemExit):
            main([DEMO, "--prices", "/nonexistent.json"])

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

    def test_extended_timeline_seven_months(self):
        tl = build_timeline(date(2026, 10, 28))
        self.assertEqual(tl.extended_end, date(2027, 7, 28))

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

    def test_effort_per_service_is_capped(self):
        huge = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {\n count = 500\n}\n'})))
        self.assertEqual(huge.effort_days[1], round(0.5 * 4 * 1.6, 1))

    def test_lockin_score_bounds(self):
        low = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {}\n'})))
        high = make_plan(scan(project({"a.tf": 'resource "aws_lambda_function" "i" {}\n'})))
        self.assertEqual((low.lockin_score, high.lockin_score), (0, 100))

    def test_effort_grows_with_resources(self):
        one = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {}\n'})))
        many = make_plan(scan(project({"a.tf": 'resource "aws_instance" "i" {\n count = 5\n}\n'})))
        self.assertGreater(many.effort_days[1], one.effort_days[1])


class TransferTests(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(transfer_hours(1000, 1000), round(1000 * 8000 / 700 / 3600, 1))
        self.assertEqual(transfer_hours(0, 1000), 0.0)
        self.assertEqual(transfer_hours(10, 0), 0.0)


class ReportTests(unittest.TestCase):
    def test_after_ban_egress_is_zero(self):
        r = scan(DEMO)
        late = make_plan(r, {"storage": 5000}, notice=date(2026, 12, 1))
        early = make_plan(r, {"storage": 5000}, notice=date(2026, 10, 28))
        self.assertEqual(totals(late, 0.92)["egress"][1], 0)
        self.assertGreater(totals(early, 0.92)["egress"][1], 0)
        self.assertIn("banned from", to_markdown(r, late))
        self.assertIn("hours", to_markdown(r, late))

    def setUp(self):
        self.result = scan(DEMO)
        self.plan = make_plan(self.result, {"storage": 2000}, monthly_bill=1000, notice=date(2026, 10, 28))

    def test_markdown_sections(self):
        md = to_markdown(self.result, self.plan)
        for part in ("Services in use", "Cost picture", "Timing", "Migration checklist", "Amazon S3", "2026-11-12"):
            self.assertIn(part, md)

    def test_unsized_report_shows_per_tb(self):
        md = to_markdown(self.result, make_plan(self.result))
        self.assertIn("No usable data sizes", md)

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


class WarningTests(unittest.TestCase):
    def test_unknown_and_unmatched_sizes_warn(self):
        r = scan(project({"a.tf": 'resource "aws_instance" "i" {}\n'}))
        plan = make_plan(r, {"storage": 100, "databse": 5, "aws_s3": 3})
        text = " ".join(plan.warnings)
        self.assertIn("storage", text)
        self.assertIn("databse: unknown", text)
        self.assertIn("aws_s3", text)
        self.assertFalse(plan.sized)
        self.assertIn("Warning", to_markdown(r, plan))

    def test_valid_sizes_no_warning(self):
        r = scan(DEMO)
        self.assertEqual(make_plan(r, {"storage": 10}).warnings, [])


class LetterTests(unittest.TestCase):
    def test_letter_per_provider(self):
        r = scan(project({"a.tf": 'resource "aws_s3_bucket" "b" {}\nresource "google_storage_bucket" "g" {}\n'}))
        text = drafts(make_plan(r), date(2026, 11, 12))
        self.assertIn("To: AWS", text)
        self.assertIn("To: Google Cloud", text)
        self.assertIn("Amazon S3", text)
        self.assertIn("2026-11-12", text)

    def test_letter_ro_and_cli(self):
        self.assertEqual(main([DEMO, "--letter", "--lang", "ro", "-o", os.devnull]), 0)
        with self.assertRaises(SystemExit):
            main([project({"x.txt": ""}), "--letter"])


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
