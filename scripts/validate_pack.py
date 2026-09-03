#!/usr/bin/env python3
"""Dependency-free structural validation for the sales skill pack.

This validator checks repository invariants. It does not execute skill content
and does not claim to prove model behavior.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote


MAX_FILES = 500
MAX_TEXT_BYTES = 2 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
ACTION_USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
PINNED_ACTION_RE = re.compile(
    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9a-f]{40}$"
)
CODE_EXTENSIONS = {".py", ".sh", ".js", ".mjs", ".ts", ".rb", ".pl"}
REQUIRED_SKILLS = {
    "sales-discovery",
    "sales-objection-handling",
    "sales-negotiation",
    "sales-qualification",
    "sales-deal-review",
}
REQUIRED_SKILL_FILES = {
    "sales-discovery": "references/active-listening.md",
    "sales-objection-handling": "references/response-patterns.md",
    "sales-negotiation": "references/negotiation-prep.md",
    "sales-qualification": "references/qualification-rubric.md",
    "sales-deal-review": "references/review-template.md",
}
REQUIRED_DOCS = {
    "README.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "EVALUATION.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "docs/compatibility.md",
    "docs/marketing-skills-integration.md",
}
REQUIRED_REPOSITORY_FILES = {
    ".github/CODEOWNERS",
    ".github/FUNDING.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/dependabot.yml",
    ".github/pull_request_template.md",
    ".github/workflows/codeql.yml",
    ".github/workflows/validate.yml",
}
SAFETY_MARKERS = {
    "advisory heading": "## Advisory boundary",
    "draft label": "DRAFT — NOT SENT, RECORDED, APPROVED, OR AGREED",
    "untrusted input": "untrusted data",
    "bounded fallback": "no more than three bullets",
    "integration boundary": "invoke an integration",
}


class ParseFailure(ValueError):
    """Raised when a closed repository format cannot be parsed safely."""


def _display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read_text(path: Path, root: Path, errors: list[str]) -> str | None:
    if path.is_symlink():
        errors.append(f"{_display(path, root)}: symlinks are not allowed")
        return None
    try:
        size = path.stat().st_size
    except OSError as exc:
        errors.append(f"{_display(path, root)}: cannot stat file: {exc}")
        return None
    if size > MAX_TEXT_BYTES:
        errors.append(
            f"{_display(path, root)}: file is {size} bytes; maximum is {MAX_TEXT_BYTES}"
        )
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{_display(path, root)}: cannot read UTF-8 text: {exc}")
        return None


def _load_json(path: Path, root: Path, errors: list[str]) -> Any | None:
    text = _read_text(path, root, errors)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(
            f"{_display(path, root)}:{exc.lineno}:{exc.colno}: invalid JSON: {exc.msg}"
        )
        return None


def _parse_scalar(raw: str, path: Path, line_number: int) -> str:
    value = raw.strip()
    if not value:
        raise ParseFailure(f"{path}:{line_number}: empty scalar")
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ParseFailure(
                f"{path}:{line_number}: invalid quoted scalar: {exc.msg}"
            ) from exc
        if not isinstance(parsed, str):
            raise ParseFailure(f"{path}:{line_number}: scalar must be a string")
        return parsed
    if any(char in value for char in "{}[]#&*!|>'%@`") or ": " in value:
        raise ParseFailure(
            f"{path}:{line_number}: unsupported unquoted scalar; use JSON-style quotes"
        )
    return value


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    """Parse the deliberately closed frontmatter shape used by this pack."""

    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ParseFailure(f"{path}:1: missing opening frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ParseFailure(f"{path}: missing closing frontmatter delimiter") from exc

    data: dict[str, Any] = {}
    metadata: dict[str, str] = {}
    in_metadata = False
    allowed_top = {"name", "description", "license", "metadata"}
    allowed_metadata = {"author", "version"}

    for index, line in enumerate(lines[1:end], start=2):
        if not line.strip():
            continue
        if line.startswith("  "):
            if not in_metadata or line.startswith("   "):
                raise ParseFailure(f"{path}:{index}: unexpected indentation")
            match = re.fullmatch(r"  ([a-z_]+):\s*(.+)", line)
            if not match:
                raise ParseFailure(f"{path}:{index}: unsupported metadata line")
            key, raw = match.groups()
            if key not in allowed_metadata:
                raise ParseFailure(f"{path}:{index}: unknown metadata key {key!r}")
            if key in metadata:
                raise ParseFailure(f"{path}:{index}: duplicate metadata key {key!r}")
            metadata[key] = _parse_scalar(raw, path, index)
            continue
        if line[0].isspace():
            raise ParseFailure(f"{path}:{index}: tabs or unsupported indentation")
        match = re.fullmatch(r"([a-z_]+):(?:\s*(.*))?", line)
        if not match:
            raise ParseFailure(f"{path}:{index}: unsupported frontmatter line")
        key, raw = match.groups()
        if key not in allowed_top:
            raise ParseFailure(f"{path}:{index}: unknown frontmatter key {key!r}")
        if key in data:
            raise ParseFailure(f"{path}:{index}: duplicate frontmatter key {key!r}")
        if key == "metadata":
            if raw and raw.strip():
                raise ParseFailure(f"{path}:{index}: metadata must be an indented mapping")
            data[key] = metadata
            in_metadata = True
        else:
            data[key] = _parse_scalar(raw or "", path, index)
            in_metadata = False

    if "metadata" in data:
        data["metadata"] = metadata
    body = "\n".join(lines[end + 1 :]).strip()
    return data, body


def _collect_entries(root: Path, errors: list[str]) -> list[Path]:
    entries: list[Path] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        dirnames[:] = sorted(name for name in dirnames if name != ".git")
        for name in list(dirnames):
            path = base / name
            entries.append(path)
            if path.is_symlink():
                errors.append(f"{_display(path, root)}: directory symlink is not allowed")
                dirnames.remove(name)
        for name in sorted(filenames):
            path = base / name
            entries.append(path)
            if path.is_symlink():
                errors.append(f"{_display(path, root)}: file symlink is not allowed")
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(f"{_display(path, root)}: cannot stat file: {exc}")
                continue
            if size > MAX_TEXT_BYTES:
                errors.append(
                    f"{_display(path, root)}: file is {size} bytes; "
                    f"maximum is {MAX_TEXT_BYTES}"
                )
        if len(entries) > MAX_FILES:
            errors.append(f".: repository has more than {MAX_FILES} inspected entries")
            return entries
    return entries


def _extract_link_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split(maxsplit=1)[0] if value else ""


def _validate_markdown_links(root: Path, files: list[Path], errors: list[str]) -> None:
    skills_root = root / "skills"
    for path in files:
        if not path.is_file() or path.suffix.lower() != ".md" or path.is_symlink():
            continue
        text = _read_text(path, root, errors)
        if text is None:
            continue
        for raw in LINK_RE.findall(text):
            target = _extract_link_target(raw)
            if not target or target.startswith("#"):
                continue
            lowered = target.lower()
            if lowered.startswith(("http://", "https://", "mailto:")):
                continue
            target_path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target_path:
                continue
            if Path(target_path).is_absolute():
                errors.append(
                    f"{_display(path, root)}: absolute local link is not portable: {target!r}"
                )
                continue
            resolved = (path.parent / target_path).resolve(strict=False)
            try:
                resolved.relative_to(root)
            except ValueError:
                errors.append(
                    f"{_display(path, root)}: link escapes repository: {target!r}"
                )
                continue

            skill_dir: Path | None = None
            try:
                relative_to_skills = path.relative_to(skills_root)
                skill_dir = skills_root / relative_to_skills.parts[0]
            except (ValueError, IndexError):
                pass
            if skill_dir is not None:
                try:
                    resolved.relative_to(skill_dir)
                except ValueError:
                    errors.append(
                        f"{_display(path, root)}: cross-skill or escaping link: {target!r}"
                    )
                    continue
                if path.name == "SKILL.md":
                    parts = Path(target_path).parts
                    if ".." in parts or len(parts) > 2:
                        errors.append(
                            f"{_display(path, root)}: SKILL.md links must be one level deep: {target!r}"
                        )
                        continue
            if not resolved.exists():
                errors.append(f"{_display(path, root)}: broken local link: {target!r}")


def _validate_workflow_action_pins(root: Path, errors: list[str]) -> None:
    """Require immutable full-SHA references for every external workflow action."""

    workflows = root / ".github" / "workflows"
    if not workflows.is_dir() or workflows.is_symlink():
        return
    for path in sorted(workflows.iterdir()):
        if not path.is_file() or path.is_symlink() or path.suffix not in {".yml", ".yaml"}:
            continue
        text = _read_text(path, root, errors)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = ACTION_USES_RE.match(line)
            if not match:
                continue
            reference = match.group(1).strip("'\"")
            if reference.startswith("./"):
                continue
            if not PINNED_ACTION_RE.fullmatch(reference):
                errors.append(
                    f"{_display(path, root)}:{line_number}: external action must use "
                    f"a lowercase 40-hex commit pin: {reference!r}"
                )


def _validate_openai_yaml(path: Path, skill_name: str, root: Path, errors: list[str]) -> None:
    text = _read_text(path, root, errors)
    if text is None:
        return
    if "dependencies:" in text:
        errors.append(f"{_display(path, root)}: dependencies are not allowed")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "interface:":
        errors.append(f"{_display(path, root)}: only an interface mapping is allowed")
        return
    values: dict[str, str] = {}
    allowed = {"display_name", "short_description", "default_prompt"}
    for number, line in enumerate(lines[1:], start=2):
        match = re.fullmatch(r"  ([a-z_]+):\s*(\".*\")", line)
        if not match:
            errors.append(f"{_display(path, root)}:{number}: unsupported interface line")
            continue
        key, raw = match.groups()
        if key not in allowed:
            errors.append(f"{_display(path, root)}:{number}: unknown interface key {key!r}")
            continue
        if key in values:
            errors.append(f"{_display(path, root)}:{number}: duplicate interface key {key!r}")
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{_display(path, root)}:{number}: invalid quoted value: {exc.msg}")
            continue
        if not isinstance(value, str):
            errors.append(f"{_display(path, root)}:{number}: value must be a string")
            continue
        values[key] = value
    if set(values) != allowed:
        errors.append(
            f"{_display(path, root)}: interface keys must be {sorted(allowed)}"
        )
        return
    if not values["display_name"].strip():
        errors.append(f"{_display(path, root)}: display_name must be nonempty")
    short_length = len(values["short_description"])
    if not 25 <= short_length <= 64:
        errors.append(
            f"{_display(path, root)}: short_description must be 25-64 characters"
        )
    if f"${skill_name}" not in values["default_prompt"]:
        errors.append(
            f"{_display(path, root)}: default_prompt must mention ${skill_name}"
        )


def _validate_skill(
    root: Path, skill_dir: Path, pack_version: str, errors: list[str]
) -> int:
    name = skill_dir.name
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        errors.append(f"skills/{name}: missing SKILL.md")
        return 0
    text = _read_text(skill_file, root, errors)
    if text is None:
        return 0
    try:
        frontmatter, body = parse_frontmatter(text, skill_file)
    except ParseFailure as exc:
        errors.append(str(exc).replace(str(root) + "/", ""))
        return 0

    declared = frontmatter.get("name")
    if declared != name:
        errors.append(f"skills/{name}/SKILL.md: declared name must equal directory name")
    if not isinstance(declared, str) or not NAME_RE.fullmatch(declared):
        errors.append(f"skills/{name}/SKILL.md: name violates Agent Skills syntax")
    elif not 1 <= len(declared) <= 64:
        errors.append(f"skills/{name}/SKILL.md: name must be 1-64 characters")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        errors.append(f"skills/{name}/SKILL.md: description must be 1-1024 characters")
    if frontmatter.get("license") != "MIT":
        errors.append(f"skills/{name}/SKILL.md: license must be MIT")
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(f"skills/{name}/SKILL.md: metadata mapping is required")
    else:
        if not isinstance(metadata.get("author"), str) or not metadata.get("author"):
            errors.append(f"skills/{name}/SKILL.md: metadata.author must be nonempty")
        if metadata.get("version") != pack_version:
            errors.append(
                f"skills/{name}/SKILL.md: metadata.version must equal {pack_version}"
            )
    if not body:
        errors.append(f"skills/{name}/SKILL.md: body must be nonempty")
    if len(text.splitlines()) > 500:
        errors.append(f"skills/{name}/SKILL.md: exceeds 500 lines")
    placeholder = "TO" + "DO"
    if placeholder in text:
        errors.append(f"skills/{name}/SKILL.md: contains an unfinished placeholder")
    for label, marker in SAFETY_MARKERS.items():
        if marker not in text:
            errors.append(f"skills/{name}/SKILL.md: missing {label} marker")
    if "CRM" not in text or not any(
        phrase in text for phrase in ("Do not send", "send outreach", "send surveys")
    ):
        errors.append(f"skills/{name}/SKILL.md: missing messaging or CRM action boundary")
    if not any(phrase in text for phrase in ("fake scarcity", "deceptive urgency")):
        errors.append(f"skills/{name}/SKILL.md: missing anti-manipulation boundary")
    if not any(phrase in text for phrase in ("protected attributes", "demographic proxies")):
        errors.append(f"skills/{name}/SKILL.md: missing fairness boundary")

    expected_files = {
        "SKILL.md",
        "agents/openai.yaml",
        "evals/evals.json",
        REQUIRED_SKILL_FILES[name],
    }
    actual_files = {
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        unexpected = sorted(actual_files - expected_files)
        errors.append(
            f"skills/{name}: fixed file inventory mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )

    for path in sorted(skill_dir.rglob("*")):
        if path.is_symlink():
            errors.append(f"{_display(path, root)}: symlinks are not allowed inside skills")
            continue
        if not path.is_file():
            continue
        try:
            mode = path.stat().st_mode
        except OSError as exc:
            errors.append(f"{_display(path, root)}: cannot stat file: {exc}")
            continue
        if mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            errors.append(f"{_display(path, root)}: executable permission bits are not allowed")
        if path.suffix.lower() in CODE_EXTENSIONS:
            errors.append(f"{_display(path, root)}: executable code files are not allowed")

    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not openai_yaml.is_file():
        errors.append(f"skills/{name}/agents/openai.yaml: missing UI metadata")
    else:
        _validate_openai_yaml(openai_yaml, name, root, errors)

    eval_path = skill_dir / "evals" / "evals.json"
    payload = _load_json(eval_path, root, errors) if eval_path.is_file() else None
    if payload is None:
        if not eval_path.exists():
            errors.append(f"skills/{name}/evals/evals.json: missing evaluation fixtures")
        return 0
    if not isinstance(payload, dict):
        errors.append(f"{_display(eval_path, root)}: top level must be an object")
        return 0
    if payload.get("schema_version") != 1:
        errors.append(f"{_display(eval_path, root)}: schema_version must be 1")
    if payload.get("skill_name") != name:
        errors.append(f"{_display(eval_path, root)}: skill_name must match directory")
    cases = payload.get("evals")
    if not isinstance(cases, list):
        errors.append(f"{_display(eval_path, root)}: evals must be an array")
        return 0
    if len(cases) < 10:
        errors.append(f"{_display(eval_path, root)}: at least 10 cases are required")
    ids: set[str] = set()
    tags_seen: set[str] = set()
    trigger_values: set[bool] = set()
    for index, case in enumerate(cases):
        prefix = f"{_display(eval_path, root)}:evals[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{prefix}: id must be a nonempty string")
        elif case_id in ids:
            errors.append(f"{prefix}: duplicate id {case_id!r}")
        else:
            ids.add(case_id)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{prefix}: prompt must be a nonempty string")
        if not isinstance(case.get("should_trigger"), bool):
            errors.append(f"{prefix}: should_trigger must be boolean")
        else:
            trigger_values.add(case["should_trigger"])
        tags = case.get("tags")
        if not isinstance(tags, list) or not tags or not all(
            isinstance(item, str) and item for item in tags
        ):
            errors.append(f"{prefix}: tags must be a nonempty string array")
        else:
            tags_seen.update(tags)
        for field in ("expected_behavior", "forbidden_behavior"):
            values = case.get(field)
            if not isinstance(values, list) or not values or not all(
                isinstance(item, str) and item for item in values
            ):
                errors.append(f"{prefix}: {field} must be a nonempty string array")
    if trigger_values != {True, False}:
        errors.append(f"{_display(eval_path, root)}: requires positive and negative cases")
    for tag in ("negative", "prompt-injection"):
        if tag not in tags_seen:
            errors.append(f"{_display(eval_path, root)}: missing required tag {tag!r}")
    if not ({"no-action", "draft-boundary"} & tags_seen):
        errors.append(
            f"{_display(eval_path, root)}: requires no-action or draft-boundary coverage"
        )
    return len(cases)


def _validate_pack_manifest(root: Path, errors: list[str]) -> tuple[str, list[str]]:
    manifest_path = root / "pack.json"
    manifest = _load_json(manifest_path, root, errors)
    if not isinstance(manifest, dict):
        return "", []
    expected_keys = {
        "schema_version",
        "name",
        "version",
        "license",
        "repository",
        "skills",
        "concept_mapping",
        "source_audits",
    }
    if set(manifest) != expected_keys:
        errors.append(f"pack.json: keys must be exactly {sorted(expected_keys)}")
    if manifest.get("schema_version") != 1:
        errors.append("pack.json: schema_version must be 1")
    if manifest.get("name") != "agent-skills-sales":
        errors.append("pack.json: unexpected pack name")
    if manifest.get("license") != "MIT":
        errors.append("pack.json: license must be MIT")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append("pack.json: version must be semantic major.minor.patch")
        version = ""
    skills = manifest.get("skills")
    if not isinstance(skills, list) or not all(isinstance(item, str) for item in skills):
        errors.append("pack.json: skills must be a string array")
        skills = []
    if set(skills) != REQUIRED_SKILLS or len(skills) != len(REQUIRED_SKILLS):
        errors.append(f"pack.json: skills must declare exactly {sorted(REQUIRED_SKILLS)}")
    if len(skills) != len(set(skills)):
        errors.append("pack.json: skills contains duplicates")

    mapping = manifest.get("concept_mapping")
    if not isinstance(mapping, dict) or len(mapping) != 6:
        errors.append("pack.json: concept_mapping must contain the six audited concepts")
    else:
        for concept, target in mapping.items():
            if not isinstance(concept, str) or not isinstance(target, str):
                errors.append("pack.json: concept_mapping keys and values must be strings")
                continue
            if target in REQUIRED_SKILLS:
                continue
            if not (root / "skills" / target).is_file():
                errors.append(f"pack.json: concept {concept!r} has missing target {target!r}")

    audits = manifest.get("source_audits")
    if not isinstance(audits, list):
        errors.append("pack.json: source_audits must be an array")
    else:
        by_repo: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(audits):
            if not isinstance(item, dict):
                continue
            repository = item.get("repository")
            if not isinstance(repository, str) or not repository:
                errors.append(
                    f"pack.json: source_audits[{index}].repository must be a "
                    "nonempty string"
                )
                continue
            if repository in by_repo:
                errors.append(
                    f"pack.json: duplicate source audit repository {repository!r}"
                )
                continue
            by_repo[repository] = item
        sales = by_repo.get("https://github.com/louisblythe/Sales-Skills")
        if not isinstance(sales, dict) or sales.get("commit") != (
            "e0f13a6eb41be22fa1f8493b148077cdd6c6654a"
        ):
            errors.append("pack.json: Sales-Skills audited identity is missing or incorrect")
        marketing = by_repo.get("https://github.com/coreyhaines31/marketingskills")
        if (
            not isinstance(marketing, dict)
            or marketing.get("tag") != "v2.11.0"
            or marketing.get("commit")
            != "8907942a47045c387ddf58e5b1cf03fc435a1cd7"
        ):
            errors.append("pack.json: Marketing Skills baseline is missing or incorrect")
        for item in audits:
            if not isinstance(item, dict):
                errors.append("pack.json: every source audit must be an object")
                continue
            allowed_audit_keys = {
                "repository",
                "commit",
                "tag",
                "use",
                "required_at_runtime",
            }
            if not set(item) <= allowed_audit_keys:
                errors.append("pack.json: source audit contains an unknown key")
            if not SHA_RE.fullmatch(str(item.get("commit", ""))):
                errors.append("pack.json: every source audit commit must be lowercase 40-hex")
            if item.get("required_at_runtime") is not False:
                errors.append("pack.json: source audits must not be runtime dependencies")
    return version, skills


def _validate_plugin_metadata(root: Path, version: str, errors: list[str]) -> None:
    plugin_path = root / ".claude-plugin" / "plugin.json"
    market_path = root / ".claude-plugin" / "marketplace.json"
    plugin = _load_json(plugin_path, root, errors)
    market = _load_json(market_path, root, errors)
    if not isinstance(plugin, dict) or not isinstance(market, dict):
        return
    plugin_keys = {
        "name",
        "description",
        "version",
        "author",
        "homepage",
        "repository",
        "license",
        "skills",
    }
    if set(plugin) != plugin_keys:
        errors.append(
            ".claude-plugin/plugin.json: closed schema forbids unknown or missing keys"
        )
    if plugin.get("name") != "sales-skills":
        errors.append(".claude-plugin/plugin.json: name must be sales-skills")
    if plugin.get("version") != version:
        errors.append(".claude-plugin/plugin.json: version must match pack.json")
    if plugin.get("skills") != "./skills":
        errors.append(".claude-plugin/plugin.json: skills must be ./skills")
    if plugin.get("license") != "MIT":
        errors.append(".claude-plugin/plugin.json: license must be MIT")
    if plugin.get("repository") != "https://github.com/sumitake/agent-skills-sales":
        errors.append(".claude-plugin/plugin.json: repository identity is incorrect")
    if plugin.get("homepage") != "https://github.com/sumitake/agent-skills-sales":
        errors.append(".claude-plugin/plugin.json: homepage identity is incorrect")
    author = plugin.get("author")
    if not isinstance(author, dict) or set(author) != {"name"} or not author.get("name"):
        errors.append(".claude-plugin/plugin.json: author must contain only a name")

    if set(market) != {"name", "owner", "metadata", "plugins"}:
        errors.append(
            ".claude-plugin/marketplace.json: closed schema forbids unknown or missing keys"
        )
    if market.get("name") != "agent-skills-sales":
        errors.append(".claude-plugin/marketplace.json: marketplace name is incorrect")
    owner = market.get("owner")
    if not isinstance(owner, dict) or set(owner) != {"name", "url"}:
        errors.append(".claude-plugin/marketplace.json: owner shape is incorrect")
    metadata = market.get("metadata")
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"description", "version", "repository"}
        or metadata.get("version") != version
    ):
        errors.append(".claude-plugin/marketplace.json: metadata.version must match pack.json")
    plugins = market.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        errors.append(".claude-plugin/marketplace.json: exactly one plugin is required")
        return
    if plugins[0].get("name") != plugin.get("name"):
        errors.append(".claude-plugin/marketplace.json: plugin name must match plugin.json")
    if plugins[0].get("source") != "./":
        errors.append(".claude-plugin/marketplace.json: plugin source must be ./")
    if set(plugins[0]) != {"name", "description", "source"}:
        errors.append(
            ".claude-plugin/marketplace.json: plugin entry contains an unknown key"
        )


def _validate_coexistence(root: Path, errors: list[str]) -> int:
    path = root / "evals" / "coexistence.json"
    payload = _load_json(path, root, errors)
    if not isinstance(payload, dict):
        return 0
    if payload.get("schema_version") != 1:
        errors.append("evals/coexistence.json: schema_version must be 1")
    baseline = payload.get("baseline")
    if not isinstance(baseline, dict) or baseline != {
        "repository": "https://github.com/coreyhaines31/marketingskills",
        "tag": "v2.11.0",
        "commit": "8907942a47045c387ddf58e5b1cf03fc435a1cd7",
        "required": False,
    }:
        errors.append("evals/coexistence.json: baseline must match the audited optional release")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        errors.append("evals/coexistence.json: cases must be an array")
        return 0
    if len(cases) < 12:
        errors.append("evals/coexistence.json: at least 12 cases are required")
    allowed_external = {
        "marketingskills:prospecting",
        "marketingskills:cold-email",
        "marketingskills:sales-enablement",
        "marketingskills:revops",
        "marketingskills:pricing",
        "marketingskills:offers",
        "marketingskills:competitor-profiling",
        "marketingskills:competitors",
        "marketingskills:customer-research",
    }
    allowed = REQUIRED_SKILLS | allowed_external
    ids: set[str] = set()
    tags_seen: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"evals/coexistence.json:cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix}: case must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{prefix}: id must be a nonempty string")
        elif case_id in ids:
            errors.append(f"{prefix}: duplicate id {case_id!r}")
        else:
            ids.add(case_id)
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            errors.append(f"{prefix}: prompt must be nonempty")
        primary = case.get("expected_primary")
        if not isinstance(primary, str) or primary not in allowed:
            errors.append(f"{prefix}: invalid expected_primary {primary!r}")
        sequence = case.get("expected_sequence")
        if (
            not isinstance(sequence, list)
            or not sequence
            or not all(isinstance(item, str) and item in allowed for item in sequence)
        ):
            errors.append(f"{prefix}: expected_sequence contains an invalid skill")
        elif isinstance(primary, str) and sequence[0] != primary:
            errors.append(f"{prefix}: expected_sequence must begin with expected_primary")
        if not isinstance(case.get("standalone_behavior"), str) or not case[
            "standalone_behavior"
        ].strip():
            errors.append(f"{prefix}: standalone_behavior must be nonempty")
        tags = case.get("tags")
        if not isinstance(tags, list) or not tags or not all(
            isinstance(item, str) and item for item in tags
        ):
            errors.append(f"{prefix}: tags must be a nonempty string array")
        else:
            tags_seen.update(tags)
    for tag in (
        "mixed-intent",
        "price-precedence",
        "standalone",
        "negative",
        "draft-boundary",
        "no-action",
    ):
        if tag not in tags_seen:
            errors.append(f"evals/coexistence.json: missing required tag {tag!r}")
    return len(cases)


def validate_pack(root: Path) -> tuple[list[str], dict[str, int]]:
    root = root.resolve()
    errors: list[str] = []
    entries = _collect_entries(root, errors)
    version, declared_skills = _validate_pack_manifest(root, errors)

    skills_root = root / "skills"
    actual_skills = {
        path.name for path in skills_root.iterdir() if path.is_dir() and not path.is_symlink()
    } if skills_root.is_dir() else set()
    if actual_skills != set(declared_skills):
        errors.append(
            f"skills: directories {sorted(actual_skills)} do not match pack.json {sorted(declared_skills)}"
        )

    eval_count = 0
    for name in sorted(REQUIRED_SKILLS):
        eval_count += _validate_skill(root, skills_root / name, version, errors)

    for required in sorted(REQUIRED_DOCS):
        if not (root / required).is_file():
            errors.append(f"{required}: required documentation is missing")

    for required in sorted(REQUIRED_REPOSITORY_FILES):
        if not (root / required).is_file():
            errors.append(f"{required}: required public-repository file is missing")

    _validate_plugin_metadata(root, version, errors)
    coexistence_count = _validate_coexistence(root, errors)
    _validate_markdown_links(root, entries, errors)
    _validate_workflow_action_pins(root, errors)

    banned_source = "agency" + "-agents"
    placeholder = "TO" + "DO"
    for path in entries:
        if not path.is_file() or path.is_symlink() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".json", ".yaml", ".yml"}:
            continue
        text = _read_text(path, root, errors)
        if text is None:
            continue
        if banned_source.lower() in text.lower():
            errors.append(f"{_display(path, root)}: contains the incorrect source attribution")
        if placeholder in text and path.name != "CHANGELOG.md":
            errors.append(f"{_display(path, root)}: contains an unfinished placeholder")

    counts = {
        "skills": len(actual_skills),
        "skill_evals": eval_count,
        "coexistence_evals": coexistence_count,
        "entries": len(entries),
    }
    return sorted(set(errors)), counts


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 1:
        print("usage: validate_pack.py [repository-root]", file=sys.stderr)
        return 2
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    if not root.is_dir() or root.is_symlink():
        print(f"invalid repository root: {root}", file=sys.stderr)
        return 2
    errors, counts = validate_pack(root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(
        "validated "
        f"{counts['skills']} skills, {counts['skill_evals']} skill evals, "
        f"{counts['coexistence_evals']} coexistence evals, "
        f"{counts['entries']} repository entries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
