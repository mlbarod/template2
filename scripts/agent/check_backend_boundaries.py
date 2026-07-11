#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
API_ROOT = ROOT_DIR / "apps" / "api" / "api"
ALLOWLIST = ROOT_DIR / "scripts" / "agent" / "backend-boundary-allowlist.txt"
API_URLS = API_ROOT / "urls.py"
COMMON_PERMISSIONS = API_ROOT / "common" / "permissions.py"
ACCOUNT_MODELS = API_ROOT / "account" / "models.py"

SHARED_DOMAINS = {"common", "data_movement.common"}
ALLOWED_APP_FILES = {
    "__init__.py",
    "apps.py",
    "models.py",
    "urls.py",
    "callback_urls.py",
    "views.py",
    "serializers.py",
    "selectors.py",
    "permissions.py",
    "admin.py",
    "tests.py",
}
ALLOWED_APP_DIRS = {"services", "migrations", "management", "__pycache__"}
ALLOWED_FACADE_MODULES = {"services", "selectors"}
WRITE_METHODS = {
    "bulk_create",
    "bulk_update",
    "create",
    "delete",
    "get_or_create",
    "update",
    "update_or_create",
}


@dataclass(frozen=True)
class Finding:
    title: str
    path: Path
    line: int
    message: str

    def render(self) -> str:
        rel_path = self.path.relative_to(ROOT_DIR)
        if self.line > 0:
            return f"{rel_path}:{self.line}: {self.message}"
        return f"{rel_path}: {self.message}"


def is_python_source(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    if "__pycache__" in path.parts:
        return False
    return True


def is_migration(path: Path) -> bool:
    return "migrations" in path.relative_to(API_ROOT).parts


def is_test_file(path: Path) -> bool:
    name = path.name
    return name == "tests.py" or name.startswith("test_")


def domain_from_path(path: Path) -> str | None:
    try:
        rel_parts = path.relative_to(API_ROOT).parts
    except ValueError:
        return None
    if not rel_parts:
        return None
    first = rel_parts[0]
    if first.endswith(".py"):
        return None
    if first == "data_movement" and len(rel_parts) >= 2 and not rel_parts[1].endswith(".py"):
        second = rel_parts[1]
        if second == "common":
            return "data_movement.common"
        return f"data_movement.{second}"
    return first


def target_domain_and_tail(module: str) -> tuple[str | None, list[str]]:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "api":
        return None, []
    if parts[1] == "data_movement":
        if len(parts) >= 3 and parts[2] == "common":
            return "data_movement.common", parts[3:]
        if len(parts) >= 3 and (API_ROOT / "data_movement" / parts[2]).is_dir():
            return f"data_movement.{parts[2]}", parts[3:]
        return "data_movement", parts[2:]
    return parts[1], parts[2:]


def imported_modules(node: ast.AST) -> list[tuple[str, int]]:
    modules: list[tuple[str, int]] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            modules.append((alias.name, node.lineno))
    elif isinstance(node, ast.ImportFrom) and node.module:
        if node.module == "api" or node.module.startswith("api."):
            _target_domain, tail = target_domain_and_tail(node.module)
            if tail:
                modules.append((node.module, node.lineno))
            else:
                for alias in node.names:
                    if alias.name == "*":
                        modules.append((node.module, node.lineno))
                    else:
                        modules.append((f"{node.module}.{alias.name}", node.lineno))
        else:
            modules.append((node.module, node.lineno))
    return modules


def is_allowed_cross_domain_import(source_domain: str | None, module: str) -> bool:
    target_domain, tail = target_domain_and_tail(module)
    if target_domain is None:
        return True
    if source_domain is None or source_domain == target_domain:
        return True
    if target_domain in SHARED_DOMAINS:
        return True
    return len(tail) == 1 and tail[0] in ALLOWED_FACADE_MODULES


def check_import_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(API_ROOT.rglob("*.py")):
        if not is_python_source(path) or is_test_file(path) or is_migration(path):
            continue
        source_domain = domain_from_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for module, line in imported_modules(node):
                if not is_allowed_cross_domain_import(source_domain, module):
                    findings.append(
                        Finding(
                            "Cross-domain internal imports",
                            path,
                            line,
                            f"cross-domain import must use services facade or selectors: {module}",
                        )
                    )
    return findings


def check_test_import_boundaries() -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(API_ROOT.rglob("*.py")):
        if not is_python_source(path) or not is_test_file(path):
            continue
        source_domain = domain_from_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for module, line in imported_modules(node):
                if not is_allowed_cross_domain_import(source_domain, module):
                    findings.append(
                        Finding(
                            "Cross-domain internal imports in tests",
                            path,
                            line,
                            f"tests must use other domains through services facade or selectors: {module}",
                        )
                    )
    return findings


def has_objects_attribute(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "objects":
            return True
    return False


def check_view_orm_usage() -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(API_ROOT.rglob("views.py")):
        if not is_python_source(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "objects":
                findings.append(
                    Finding(
                        "Direct ORM usage in views",
                        path,
                        node.lineno,
                        "views.py must call selectors/services instead of direct ORM queries",
                    )
                )
    return findings


def check_selector_writes() -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(API_ROOT.rglob("selectors.py")):
        if not is_python_source(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in WRITE_METHODS:
                continue
            if has_objects_attribute(func.value):
                findings.append(
                    Finding(
                        "Write ORM usage in selectors",
                        path,
                        node.lineno,
                        f"selectors.py must stay read-only: {func.attr}()",
                    )
                )
    return findings


def check_app_directory(app_dir: Path, app_label: str) -> list[Finding]:
    findings: list[Finding] = []
    for child in sorted(app_dir.iterdir()):
        if child.name == "__pycache__":
            continue
        if child.is_file():
            if child.name not in ALLOWED_APP_FILES and not child.name.startswith("test_"):
                findings.append(
                    Finding(
                        "Disallowed backend app files",
                        child,
                        0,
                        f"{app_label} has a non-standard file; add a rule before using it",
                    )
                )
            continue
        if child.is_dir() and child.name == "management":
            findings.extend(check_domain_management_directory(child, app_label))
            continue
        if child.is_dir() and child.name not in ALLOWED_APP_DIRS:
            findings.append(
                Finding(
                    "Disallowed backend app directories",
                    child,
                    0,
                    f"{app_label} has a non-standard directory; use allowed domain folders only",
                )
            )
    return findings


def check_domain_management_directory(management_dir: Path, app_label: str) -> list[Finding]:
    findings: list[Finding] = []
    allowed = {"commands", "__pycache__"}
    for child in sorted(management_dir.iterdir()):
        if child.name in allowed or child.name == "__init__.py":
            continue
        findings.append(
            Finding(
                "Disallowed backend management directories",
                child,
                0,
                f"{app_label} management/ may contain commands/ only",
            )
        )
    return findings


def check_app_structure() -> list[Finding]:
    findings: list[Finding] = []
    for child in sorted(API_ROOT.iterdir()):
        if child.name in {"__pycache__", "migrations"} or child.name.endswith(".py"):
            continue
        if not child.is_dir():
            continue
        if child.name == "data_movement":
            for nested in sorted(child.iterdir()):
                if nested.name == "__pycache__" or nested.name.endswith(".py"):
                    continue
                if nested.is_dir() and nested.name != "common":
                    findings.extend(check_app_directory(nested, f"data_movement.{nested.name}"))
            continue
        if child.name == "management":
            allowed_management_dirs = {"commands", "services", "__pycache__"}
            for nested in sorted(child.iterdir()):
                if nested.name == "__pycache__":
                    continue
                if nested.is_file():
                    if nested.name not in ALLOWED_APP_FILES:
                        findings.append(
                            Finding(
                                "Disallowed backend app files",
                                nested,
                                0,
                                "management has a non-standard file; add a rule before using it",
                            )
                        )
                    continue
                if nested.is_dir() and nested.name not in allowed_management_dirs:
                    findings.append(
                        Finding(
                            "Disallowed backend app directories",
                            nested,
                            0,
                            "management has a non-standard directory; use allowed management folders only",
                        )
                    )
            continue
        findings.extend(check_app_directory(child, child.name))
    return findings


def load_literal_assignment(path: Path, name: str) -> tuple[Any, int]:
    """모듈의 단순 리터럴 대입 값을 정적 분석용으로 읽습니다."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        return ast.literal_eval(node.value), node.lineno
    raise ValueError(f"{path}: missing literal assignment: {name}")


def list_root_api_routes() -> dict[str, int]:
    """전역 URL registry의 `/api/v1/<route>/` 루트와 줄 번호를 반환합니다."""

    tree = ast.parse(API_URLS.read_text(encoding="utf-8"), filename=str(API_URLS))
    routes: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "path":
            continue
        route_arg = node.args[0]
        if not isinstance(route_arg, ast.Constant) or not isinstance(route_arg.value, str):
            continue
        route_path = route_arg.value
        if not route_path.startswith("api/v1/"):
            continue
        route = route_path.removeprefix("api/v1/").strip("/").split("/", maxsplit=1)[0]
        if route:
            routes[route] = node.lineno
    return routes


def check_api_route_access_classification() -> list[Finding]:
    """모든 루트 API 경로와 앱 scope 참조가 유효한지 확인합니다."""

    findings: list[Finding] = []
    try:
        policies, policy_line = load_literal_assignment(COMMON_PERMISSIONS, "API_ROUTE_ACCESS_POLICIES")
        app_rules, app_rules_line = load_literal_assignment(COMMON_PERMISSIONS, "APP_ACCESS_API_RULES")
        app_scope_keys, app_scope_keys_line = load_literal_assignment(ACCOUNT_MODELS, "SYSTEM_APP_SCOPE_KEYS")
    except (SyntaxError, ValueError) as exc:
        return [Finding("API route access classification", COMMON_PERMISSIONS, 0, str(exc))]

    if not isinstance(policies, dict):
        return [
            Finding(
                "API route access classification",
                COMMON_PERMISSIONS,
                policy_line,
                "API_ROUTE_ACCESS_POLICIES must be a literal dict",
            )
        ]
    if not isinstance(app_rules, tuple):
        return [
            Finding(
                "API route access classification",
                COMMON_PERMISSIONS,
                app_rules_line,
                "APP_ACCESS_API_RULES must be a literal tuple",
            )
        ]
    if not isinstance(app_scope_keys, tuple) or not all(isinstance(value, str) for value in app_scope_keys):
        return [
            Finding(
                "API route access classification",
                ACCOUNT_MODELS,
                app_scope_keys_line,
                "SYSTEM_APP_SCOPE_KEYS must be a literal string tuple",
            )
        ]
    known_app_scopes = set(app_scope_keys)

    routes = list_root_api_routes()
    policy_routes = set(policies)
    for route in sorted(set(routes) - policy_routes):
        findings.append(
            Finding(
                "API route access classification",
                API_URLS,
                routes[route],
                f"/api/v1/{route}/ must declare public, token, portal, or app:<scope> access",
            )
        )
    for route in sorted(policy_routes - set(routes)):
        findings.append(
            Finding(
                "API route access classification",
                COMMON_PERMISSIONS,
                policy_line,
                f"access policy references an unknown root route: {route}",
            )
        )

    for rule in app_rules:
        if (
            not isinstance(rule, tuple)
            or len(rule) != 2
            or not all(isinstance(value, str) for value in rule)
        ):
            findings.append(
                Finding(
                    "API route access classification",
                    COMMON_PERMISSIONS,
                    app_rules_line,
                    "each APP_ACCESS_API_RULES entry must be a (prefix, scope) string tuple",
                )
            )
            continue
        prefix, scope = rule
        if scope not in known_app_scopes:
            findings.append(
                Finding(
                    "API route access classification",
                    COMMON_PERMISSIONS,
                    app_rules_line,
                    f"app access rule references an unknown system scope: {scope}",
                )
            )
        if not prefix.startswith("/api/v1/"):
            findings.append(
                Finding(
                    "API route access classification",
                    COMMON_PERMISSIONS,
                    app_rules_line,
                    f"app access prefix must start with /api/v1/: {prefix}",
                )
            )
            continue
        route = prefix.removeprefix("/api/v1/").split("/", maxsplit=1)[0]
        if route not in routes:
            findings.append(
                Finding(
                    "API route access classification",
                    COMMON_PERMISSIONS,
                    app_rules_line,
                    f"app access rule references an unknown root route: {prefix}",
                )
            )
        elif policies.get(route) != "portal":
            findings.append(
                Finding(
                    "API route access classification",
                    COMMON_PERMISSIONS,
                    app_rules_line,
                    f"{prefix} override requires a portal root route, got {policies.get(route)!r}",
                )
            )

    for route, policy in sorted(policies.items()):
        if policy in {"public", "token", "portal"}:
            continue
        if not isinstance(policy, str) or not policy.startswith("app:") or not policy.removeprefix("app:"):
            findings.append(
                Finding(
                    "API route access classification",
                    COMMON_PERMISSIONS,
                    policy_line,
                    f"invalid access policy for {route}: {policy!r}",
                )
            )
            continue
        scope = policy.removeprefix("app:")
        if scope not in known_app_scopes:
            findings.append(
                Finding(
                    "API route access classification",
                    ACCOUNT_MODELS,
                    app_scope_keys_line,
                    f"app route {route} references an unknown system scope: {scope}",
                )
            )
    return findings


def load_allowlist() -> list[re.Pattern[str]]:
    if not ALLOWLIST.exists():
        return []
    patterns: list[re.Pattern[str]] = []
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(re.compile(stripped))
    return patterns


def filter_allowlisted(findings: list[Finding], patterns: list[re.Pattern[str]]) -> list[Finding]:
    if not patterns:
        return findings
    filtered: list[Finding] = []
    for finding in findings:
        rendered = finding.render()
        if any(pattern.search(rendered) for pattern in patterns):
            continue
        filtered.append(finding)
    return filtered


def print_section(title: str, findings: list[Finding]) -> int:
    print(f"== {title} ==")
    if findings:
        for finding in findings:
            print(finding.render())
        print()
        return 1
    print("OK\n")
    return 0


def main() -> int:
    if not API_ROOT.exists():
        print("Missing backend source directory: apps/api/api", file=sys.stderr)
        return 2

    status = 0
    allowlist_patterns = load_allowlist()
    checks = [
        ("Cross-domain internal imports", filter_allowlisted(check_import_boundaries(), allowlist_patterns)),
        ("Cross-domain internal imports in tests", filter_allowlisted(check_test_import_boundaries(), allowlist_patterns)),
        ("Direct ORM usage in views", filter_allowlisted(check_view_orm_usage(), allowlist_patterns)),
        ("Write ORM usage in selectors", filter_allowlisted(check_selector_writes(), allowlist_patterns)),
        (
            "API route access classification",
            filter_allowlisted(check_api_route_access_classification(), allowlist_patterns),
        ),
        ("Backend app structure", filter_allowlisted(check_app_structure(), allowlist_patterns)),
    ]
    for title, findings in checks:
        status |= print_section(title, findings)

    if status == 0:
        print("Backend boundary audit passed.")
    else:
        print("Backend boundary audit found review candidates.")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
