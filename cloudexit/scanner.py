"""Find cloud services in Terraform, Docker, compose, env and dependency files.

Only names, resource types and file locations are recorded. Values of environment
variables are matched against endpoint patterns but never stored or printed.
"""
import json
import os
import re
from dataclasses import dataclass, field

from .catalog import (ENDPOINT_RULES, ENV_KEY_RULES, IMAGE_RULES, RISK_PATTERNS,
                      SDK_RULES, SERVICES, TERRAFORM_RULES)

SKIP_DIRS = {".git", "node_modules", ".terraform", ".venv", "venv", "__pycache__", "vendor", "dist", "build"}
MAX_BYTES = 2_000_000

RESOURCE_RE = re.compile(r'^\s*(resource|data)\s+"([A-Za-z0-9_]+)"\s+"([^"]+)"\s*\{', re.M)
BACKEND_RE = re.compile(r'^\s*backend\s+"(s3|azurerm|gcs)"', re.M)
ENV_LINE_RE = re.compile(r"""^\s*(?:-\s*)?(?:export\s+)?["']?([A-Za-z_][A-Za-z0-9_]*)["']?\s*[=:]\s*(.*)$""")
IMAGE_LINE_RE = re.compile(r"^\s*image:\s*[\"']?([^\s\"'#]+)")
FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)?(\S+)", re.I)
PORTABLE_IMAGES = re.compile(r"^(?:docker\.io/)?(?:library/)?(postgres|mysql|mariadb|redis|valkey|memcached|mongo|rabbitmq|nats|minio/minio|nginx|traefik|caddy|grafana|prom|keycloak|clickhouse|elasticsearch|opensearch)")


@dataclass
class Evidence:
    file: str
    line: int
    kind: str
    detail: str


@dataclass
class Finding:
    service_key: str
    evidence: list = field(default_factory=list)
    resources: int = 0

    @property
    def service(self):
        return SERVICES[self.service_key]


@dataclass
class ScanResult:
    root: str
    findings: dict = field(default_factory=dict)
    providers: set = field(default_factory=set)
    infra_only: dict = field(default_factory=dict)
    risks: list = field(default_factory=list)
    portable_images: set = field(default_factory=set)
    files_scanned: int = 0
    state_backends: set = field(default_factory=set)

    def add(self, key, file, line, kind, detail, count=1):
        f = self.findings.setdefault(key, Finding(key))
        f.evidence.append(Evidence(file, line, kind, detail))
        f.resources += count
        self.providers.add(SERVICES[key].provider)


def _lineno(text, pos):
    return text.count("\n", 0, pos) + 1


TF_RULES = [(pattern, provider, key) for provider, pattern, key in TERRAFORM_RULES]


def _first_rule(rules, value):
    """Rules are (pattern, provider, service key) tuples; returns (provider, key) of the first match."""
    for pattern, provider, key in rules:
        if re.search(pattern, value):
            return provider, key
    return None


def strip_hcl_comments(text):
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"(?m)(?:#|//).*$", "", text)


def _block_body(text, start):
    depth, i = 0, text.index("{", start)
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    return text[i:]


def scan_terraform(result, path, rel, text):
    text = strip_hcl_comments(text)
    for m in RESOURCE_RE.finditer(text):
        kind, rtype, name = m.groups()
        hit = _first_rule(TF_RULES, rtype)
        if not hit:
            continue
        provider, key = hit
        line = _lineno(text, m.start())
        if key is None:
            result.providers.add(provider)
            result.infra_only[rtype] = result.infra_only.get(rtype, 0) + 1
            continue
        body = _block_body(text, m.start())
        count = 1
        cm = re.search(r"\bcount\s*=\s*(\d+)\b", body)
        if cm and kind == "resource":
            count = max(1, int(cm.group(1)))
        if kind == "resource":
            result.add(key, rel, line, "terraform", f"{rtype}.{name}", count)
            for pattern, message in RISK_PATTERNS:
                if re.search(pattern, body):
                    result.risks.append((rel, line, f"{rtype}.{name}", message))
        else:
            result.add(key, rel, line, "terraform-data", f"data.{rtype}.{name}", 0)
    for m in BACKEND_RE.finditer(text):
        result.state_backends.add(m.group(1))


def scan_tfstate(result, path, rel, text):
    try:
        data = json.loads(text)
    except ValueError:
        return
    for res in data.get("resources", []):
        if res.get("mode") != "managed":
            continue
        hit = _first_rule(TF_RULES, res.get("type", ""))
        if not hit:
            continue
        provider, key = hit
        n = len(res.get("instances", [])) or 1
        if key is None:
            result.providers.add(provider)
            result.infra_only[res["type"]] = result.infra_only.get(res["type"], 0) + n
        else:
            result.add(key, rel, 0, "tfstate", f"{res['type']}.{res.get('name', '?')}", n)


def _scan_image(result, rel, line, image, kind):
    hit = _first_rule(IMAGE_RULES, image)
    if hit:
        result.add(hit[1], rel, line, kind, f"image {image}")
    elif PORTABLE_IMAGES.match(image):
        result.portable_images.add(image.split(":")[0])


def scan_env_like(result, rel, text):
    for n, raw in enumerate(text.splitlines(), 1):
        if raw.lstrip().startswith("#"):
            continue
        m = IMAGE_LINE_RE.match(raw)
        if m:
            _scan_image(result, rel, n, m.group(1), "compose-image")
            continue
        m = ENV_LINE_RE.match(raw)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        hit = _first_rule(ENV_KEY_RULES, key)
        if hit:
            result.add(hit[1], rel, n, "env-key", key, 0)
        hit = _first_rule(ENDPOINT_RULES, value)
        if hit:
            result.add(hit[1], rel, n, "endpoint", f"{key} points at a {SERVICES[hit[1]].name} endpoint", 0)


def scan_dockerfile(result, rel, text):
    for n, raw in enumerate(text.splitlines(), 1):
        m = FROM_RE.match(raw)
        if m and m.group(1).lower() != "scratch":
            _scan_image(result, rel, n, m.group(1), "dockerfile-from")
    env_lines = []
    for raw in text.splitlines():
        m = re.match(r"\s*ENV\s+(.*)$", raw, re.I)
        if m:
            body = m.group(1)
            env_lines.append(body if "=" in body else re.sub(r"\s+", "=", body, count=1))
    scan_env_like(result, rel, "\n".join(env_lines))


def scan_requirements(result, rel, text):
    for n, raw in enumerate(text.splitlines(), 1):
        name = re.split(r"[<>=!~\[; ]", raw.strip(), maxsplit=1)[0].lower()
        if not name or name.startswith(("#", "-")):
            continue
        _sdk(result, rel, n, name)


def scan_package_json(result, rel, text):
    try:
        data = json.loads(text)
    except ValueError:
        return
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name in data.get(section, {}):
            _sdk(result, rel, 0, name.lower())


def _sdk(result, rel, line, name):
    hit = _first_rule(SDK_RULES, name)
    if hit:
        result.add(hit[1], rel, line, "sdk", f"dependency {name}", 0)


def classify(name):
    low = name.lower()
    if low.endswith(".tf"):
        return "terraform"
    if low.endswith(".tfstate"):
        return "tfstate"
    if low == "dockerfile" or low.startswith("dockerfile.") or low.endswith(".dockerfile"):
        return "dockerfile"
    if re.match(r"^(docker-)?compose[\w.-]*\.ya?ml$", low):
        return "compose"
    if low == ".env" or low.startswith(".env.") or low.endswith(".env"):
        return "env"
    if re.match(r"^requirements[\w.-]*\.txt$", low):
        return "requirements"
    if low == "package.json":
        return "package"
    return None


def scan(root):
    result = ScanResult(root=os.path.abspath(root))
    paths = [root] if os.path.isfile(root) else None
    if paths is None:
        paths = []
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            paths += [os.path.join(dirpath, f) for f in sorted(files)]
    base = os.path.dirname(os.path.abspath(root)) if os.path.isfile(root) else root
    for path in paths:
        kind = classify(os.path.basename(path))
        if not kind or os.path.getsize(path) > MAX_BYTES:
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        rel = os.path.relpath(path, base)
        result.files_scanned += 1
        if kind == "terraform":
            scan_terraform(result, path, rel, text)
        elif kind == "tfstate":
            scan_tfstate(result, path, rel, text)
        elif kind == "dockerfile":
            scan_dockerfile(result, rel, text)
        elif kind in ("compose", "env"):
            scan_env_like(result, rel, text)
        elif kind == "requirements":
            scan_requirements(result, rel, text)
        elif kind == "package":
            scan_package_json(result, rel, text)
    for backend, provider in (("s3", "aws"), ("azurerm", "azure"), ("gcs", "gcp")):
        if backend in result.state_backends:
            result.providers.add(provider)
    return result
