from __future__ import annotations

import importlib.util
import json
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock


REPOSITORY = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validate_pack = load_module("validate_pack", REPOSITORY / "scripts/validate_pack.py")
source_overlap = load_module(
    "check_source_overlap", REPOSITORY / "scripts/check_source_overlap.py"
)


class PackValidationTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repository"
        shutil.copytree(
            REPOSITORY,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def errors(self) -> list[str]:
        return validate_pack.validate_pack(self.root)[0]

    def append(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_repository_is_valid(self) -> None:
        self.assertEqual([], self.errors())

    def test_frontmatter_parser_accepts_closed_shape(self) -> None:
        parsed, body = validate_pack.parse_frontmatter(
            '---\nname: sample\ndescription: "Example"\nlicense: MIT\nmetadata:\n'
            '  author: Test\n  version: "1.0.0"\n---\nBody\n',
            Path("SKILL.md"),
        )
        self.assertEqual("sample", parsed["name"])
        self.assertEqual("1.0.0", parsed["metadata"]["version"])
        self.assertEqual("Body", body)

    def test_invalid_declared_name_is_rejected(self) -> None:
        path = self.root / "skills/sales-discovery/SKILL.md"
        text = path.read_text(encoding="utf-8").replace(
            "name: sales-discovery", "name: Sales_Discovery", 1
        )
        path.write_text(text, encoding="utf-8")
        self.assertTrue(any("name violates" in error for error in self.errors()))

    def test_broken_link_is_rejected(self) -> None:
        self.append("skills/sales-discovery/SKILL.md", "\n[missing](references/nope.md)\n")
        self.assertTrue(any("broken local link" in error for error in self.errors()))

    def test_traversal_link_is_rejected(self) -> None:
        self.append("skills/sales-discovery/SKILL.md", "\n[escape](../../../outside.md)\n")
        self.assertTrue(any("link escapes repository" in error for error in self.errors()))

    def test_cross_skill_link_is_rejected(self) -> None:
        self.append(
            "skills/sales-discovery/SKILL.md",
            "\n[cross](../sales-negotiation/SKILL.md)\n",
        )
        self.assertTrue(any("cross-skill" in error for error in self.errors()))

    def test_skill_symlink_is_rejected(self) -> None:
        link = self.root / "skills/sales-discovery/references/linked.md"
        link.symlink_to("active-listening.md")
        self.assertTrue(any("symlink" in error for error in self.errors()))

    def test_required_skill_directory_symlink_stops_semantic_validation(self) -> None:
        skill = self.root / "skills/sales-discovery"
        external = Path(self.temporary.name) / "external-skill"
        shutil.move(skill, external)
        skill.symlink_to(external, target_is_directory=True)
        with mock.patch.object(
            Path, "rglob", side_effect=AssertionError("semantic traversal")
        ):
            errors, counts = validate_pack.validate_pack(self.root)
        self.assertTrue(any("symlink" in error for error in errors))
        self.assertEqual(0, counts["skills"])

    def test_executable_skill_resource_is_rejected(self) -> None:
        path = self.root / "skills/sales-discovery/references/active-listening.md"
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.assertTrue(any("executable permission" in error for error in self.errors()))

    def test_missing_safety_boundary_is_rejected(self) -> None:
        path = self.root / "skills/sales-discovery/SKILL.md"
        text = path.read_text(encoding="utf-8").replace("## Advisory boundary", "")
        path.write_text(text, encoding="utf-8")
        self.assertTrue(any("advisory heading" in error for error in self.errors()))

    def test_malformed_eval_json_is_rejected(self) -> None:
        path = self.root / "skills/sales-discovery/evals/evals.json"
        path.write_text("{", encoding="utf-8")
        self.assertTrue(any("invalid JSON" in error for error in self.errors()))

    def test_deeply_nested_json_is_rejected_without_crashing(self) -> None:
        path = self.root / "pack.json"
        path.write_text("[" * 2_000 + "]" * 2_000, encoding="utf-8")
        self.assertTrue(any("nesting exceeds" in error for error in self.errors()))

    def test_missing_eval_tag_is_rejected(self) -> None:
        path = self.root / "skills/sales-discovery/evals/evals.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload["evals"]:
            case["tags"] = [tag for tag in case["tags"] if tag != "prompt-injection"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("prompt-injection" in error for error in self.errors()))

    def test_pack_version_mismatch_is_rejected(self) -> None:
        path = self.root / "pack.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["version"] = "1.0.1"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("version must equal" in error for error in self.errors()))

    def test_exact_concept_mapping_is_required(self) -> None:
        path = self.root / "pack.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["concept_mapping"]["pipeline"] = payload["concept_mapping"].pop(
            "discovery"
        )
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(
            any("exact audited concept map" in error for error in self.errors())
        )

    def test_non_string_source_repository_is_rejected_without_crashing(self) -> None:
        path = self.root / "pack.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["source_audits"][0]["repository"] = ["not", "a", "string"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("repository must be" in error for error in self.errors()))

    def test_openai_unknown_field_is_rejected(self) -> None:
        self.append(
            "skills/sales-discovery/agents/openai.yaml",
            '  unexpected: "value"\n',
        )
        self.assertTrue(any("unknown interface key" in error for error in self.errors()))

    def test_unexpected_skill_payload_is_rejected(self) -> None:
        path = self.root / "skills/sales-discovery/references/hidden.txt"
        path.write_text("unexpected", encoding="utf-8")
        self.assertTrue(any("file inventory mismatch" in error for error in self.errors()))

    def test_unexpected_skill_directory_is_rejected_without_crashing(self) -> None:
        path = self.root / "skills/unexpected-skill"
        path.mkdir()
        self.assertTrue(any("do not match pack.json" in error for error in self.errors()))

    def test_plugin_execution_surface_is_rejected(self) -> None:
        path = self.root / ".claude-plugin/plugin.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["mcpServers"] = {"unsafe": {"command": "example"}}
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("closed schema" in error for error in self.errors()))

    def test_missing_coexistence_coverage_is_rejected(self) -> None:
        path = self.root / "evals/coexistence.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload["cases"]:
            case["tags"] = [tag for tag in case["tags"] if tag != "price-precedence"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("price-precedence" in error for error in self.errors()))

    def test_non_string_coexistence_primary_is_rejected_without_crashing(self) -> None:
        path = self.root / "evals/coexistence.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["expected_primary"] = {"skill": "sales-discovery"}
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("invalid expected_primary" in error for error in self.errors()))

    def test_non_string_coexistence_sequence_is_rejected_without_crashing(self) -> None:
        path = self.root / "evals/coexistence.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["cases"][0]["expected_sequence"] = [{"skill": "sales-discovery"}]
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertTrue(any("invalid skill" in error for error in self.errors()))

    def test_mutable_workflow_action_reference_is_rejected(self) -> None:
        path = self.root / ".github/workflows/validate.yml"
        text = path.read_text(encoding="utf-8").replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/checkout@v7",
            1,
        )
        path.write_text(text, encoding="utf-8")
        self.assertTrue(any("40-hex commit pin" in error for error in self.errors()))

    def test_alternate_yaml_action_keys_cannot_bypass_pin_check(self) -> None:
        path = self.root / ".github/workflows/validate.yml"
        original = path.read_text(encoding="utf-8")
        canonical = (
            "      - name: Check out repository\n"
            "        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
        )
        variants = (
            "      - name: Check out repository\n"
            "        \"uses\": actions/checkout@main",
            "      - name: Check out repository\n"
            "        uses : actions/checkout@main",
            "      - {name: Check out repository, uses: actions/checkout@main}",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                path.write_text(original.replace(canonical, variant, 1), encoding="utf-8")
                self.assertTrue(
                    any("40-hex commit pin" in error for error in self.errors())
                )
        path.write_text(original, encoding="utf-8")

    def test_invalid_decoded_link_path_is_rejected_without_crashing(self) -> None:
        self.append("README.md", "\n[invalid](%00)\n")
        self.assertTrue(any("invalid local link path" in error for error in self.errors()))

    def test_repository_file_bound_stops_before_skill_traversal(self) -> None:
        generated = self.root / "skills/sales-discovery/generated"
        generated.mkdir()
        for index in range(validate_pack.MAX_ENTRIES):
            (generated / f"{index:04d}.txt").write_text("x", encoding="utf-8")
        with mock.patch.object(Path, "rglob", side_effect=AssertionError("unbounded")):
            errors, counts = validate_pack.validate_pack(self.root)
        self.assertTrue(any("more than" in error for error in errors))
        self.assertEqual(0, counts["skills"])
        with mock.patch("builtins.print"):
            self.assertEqual(1, validate_pack.main([str(self.root)]))

    def test_unreadable_inventory_fails_before_semantic_validation(self) -> None:
        blocked = self.root / "blocked"
        blocked.mkdir()
        blocked = blocked.resolve()
        real_scandir = validate_pack.os.scandir

        def guarded_scandir(path):
            if Path(path).resolve() == blocked:
                raise PermissionError("synthetic denial")
            return real_scandir(path)

        with mock.patch.object(
            validate_pack.os, "scandir", side_effect=guarded_scandir
        ):
            errors, counts = validate_pack.validate_pack(self.root)
        self.assertTrue(any("cannot scan directory" in error for error in errors))
        self.assertEqual(0, counts["skills"])

    def test_invalid_utf8_text_is_rejected_without_crashing(self) -> None:
        (self.root / "README.md").write_bytes(b"\xff")
        self.assertTrue(any("cannot decode UTF-8" in error for error in self.errors()))

    def test_oversized_text_read_is_rejected(self) -> None:
        (self.root / "README.md").write_bytes(
            b"x" * (validate_pack.MAX_TEXT_BYTES + 1)
        )
        self.assertTrue(
            any(
                "maximum" in error or "exceeds" in error
                for error in self.errors()
            )
        )

    def test_missing_public_repository_file_is_rejected(self) -> None:
        (self.root / ".github/CODEOWNERS").unlink()
        self.assertTrue(
            any("required public-repository file" in error for error in self.errors())
        )


class SourceOverlapTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.source.mkdir()
        self.target.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def scan(self, path: Path, **kwargs):
        return source_overlap.scan_markdown(path, **kwargs)

    def test_exact_overlap_is_reported(self) -> None:
        (self.source / "a.md").write_text("one two three four five", encoding="utf-8")
        (self.target / "b.md").write_text("zero two three four nine", encoding="utf-8")
        result = source_overlap.find_overlaps(
            self.scan(self.source), self.scan(self.target), window=3
        )
        self.assertEqual(1, result.total)
        self.assertEqual(
            ["two three four"], [item.phrase for item in result.samples]
        )

    def test_clean_trees_return_no_overlap(self) -> None:
        (self.source / "a.md").write_text("one two three", encoding="utf-8")
        (self.target / "b.md").write_text("four five six", encoding="utf-8")
        self.assertEqual(
            0,
            source_overlap.find_overlaps(
                self.scan(self.source), self.scan(self.target), window=2
            ).total,
        )

    def test_unicode_normalization_and_casefold_are_applied(self) -> None:
        (self.source / "a.md").write_text("ＣＡＦÉ Value", encoding="utf-8")
        (self.target / "b.md").write_text("café value", encoding="utf-8")
        result = source_overlap.find_overlaps(
            self.scan(self.source), self.scan(self.target), window=2
        )
        self.assertEqual("café value", result.samples[0].phrase)

    def test_reports_are_capped_while_total_remains_exact(self) -> None:
        text = "one two three four five"
        (self.source / "a.md").write_text(text, encoding="utf-8")
        (self.target / "b.md").write_text(text, encoding="utf-8")
        result = source_overlap.find_overlaps(
            self.scan(self.source), self.scan(self.target), window=2, max_reports=1
        )
        self.assertEqual(4, result.total)
        self.assertEqual(1, len(result.samples))

    def test_digest_collisions_preserve_exact_matches(self) -> None:
        (self.source / "a.md").write_text("one two red blue", encoding="utf-8")
        (self.target / "b.md").write_text("red blue", encoding="utf-8")
        original = source_overlap._window_digest
        source_overlap._window_digest = lambda tokens, start, window: b"collision"
        try:
            result = source_overlap.find_overlaps(
                self.scan(self.source), self.scan(self.target), window=2
            )
        finally:
            source_overlap._window_digest = original
        self.assertEqual(1, result.total)
        self.assertEqual("red blue", result.samples[0].phrase)

    def test_symlink_is_rejected(self) -> None:
        (self.source / "real.md").write_text("text", encoding="utf-8")
        (self.source / "link.md").symlink_to("real.md")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source)

    def test_symlinked_root_is_rejected(self) -> None:
        linked = self.root / "linked-source"
        linked.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(source_overlap.ScanError):
            self.scan(linked)

    def test_entry_count_bound_includes_non_markdown_and_directories(self) -> None:
        nested = self.source / "nested"
        nested.mkdir()
        (self.source / "ignored.txt").write_text("one", encoding="utf-8")
        (nested / "also-ignored.txt").write_text("two", encoding="utf-8")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source, max_entries=2)

    def test_markdown_entry_count_bound_is_enforced(self) -> None:
        (self.source / "one.md").write_text("one", encoding="utf-8")
        (self.source / "two.md").write_text("two", encoding="utf-8")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source, max_entries=1)

    def test_git_metadata_is_pruned_but_other_hidden_content_is_scanned(self) -> None:
        metadata = self.source / ".git"
        metadata.mkdir()
        for index in range(10):
            (metadata / str(index)).write_text("metadata", encoding="utf-8")
        hidden = self.source / ".hidden"
        hidden.mkdir()
        (hidden / "included.md").write_text("included", encoding="utf-8")
        documents = self.scan(self.source, max_entries=3)
        self.assertEqual(
            [Path(".hidden/included.md")], [item.path for item in documents]
        )

    def test_unreadable_directory_is_a_terminal_scan_error(self) -> None:
        blocked = self.source / "blocked"
        blocked.mkdir()
        blocked = blocked.resolve()
        real_scandir = source_overlap.os.scandir

        def guarded_scandir(path):
            if Path(path).resolve() == blocked:
                raise PermissionError("synthetic denial")
            return real_scandir(path)

        with mock.patch.object(
            source_overlap.os, "scandir", side_effect=guarded_scandir
        ):
            with self.assertRaises(source_overlap.ScanError):
                self.scan(self.source)

    def test_invalid_utf8_markdown_is_a_terminal_scan_error(self) -> None:
        (self.source / "invalid.md").write_bytes(b"\xff")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source)

    def test_document_order_is_deterministic(self) -> None:
        (self.source / "b.md").write_text("b", encoding="utf-8")
        (self.source / "a.md").write_text("a", encoding="utf-8")
        self.assertEqual(
            [Path("a.md"), Path("b.md")],
            [item.path for item in self.scan(self.source)],
        )

    def test_max_files_cli_name_remains_an_alias(self) -> None:
        args = source_overlap.build_parser().parse_args(
            ["--source", "source", "--target", "target", "--max-files", "7"]
        )
        self.assertEqual(7, args.max_entries)

    def test_file_size_bound_is_enforced(self) -> None:
        (self.source / "large.md").write_text("12345", encoding="utf-8")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source, max_file_bytes=4)

    def test_total_size_bound_is_enforced(self) -> None:
        (self.source / "one.md").write_text("123", encoding="utf-8")
        (self.source / "two.md").write_text("456", encoding="utf-8")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source, max_total_bytes=5)

    def test_token_count_bound_is_enforced(self) -> None:
        (self.source / "tokens.md").write_text("one two", encoding="utf-8")
        with self.assertRaises(source_overlap.ScanError):
            self.scan(self.source, max_tokens=1)

    def test_window_size_bound_is_enforced(self) -> None:
        with self.assertRaises(source_overlap.ScanError):
            source_overlap.find_overlaps(
                [], [], window=source_overlap.MAX_WINDOW + 1
            )


if __name__ == "__main__":
    main()
