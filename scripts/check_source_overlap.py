#!/usr/bin/env python3
"""Report exact normalized prose-window overlap between two Markdown trees.

This is a bounded accidental-copying screen, not a legal conclusion. It never
executes content from either tree.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


DEFAULT_WINDOW = 12
DEFAULT_MAX_FILES = 2_000
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_REPORTS = 100
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


class ScanError(ValueError):
    """Raised when an input tree violates a scanner bound."""


@dataclass(frozen=True)
class Document:
    path: Path
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class Overlap:
    phrase: str
    source_path: Path
    target_path: Path


def _tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(TOKEN_RE.findall(normalized))


def scan_markdown(
    root: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> list[Document]:
    """Read a bounded Markdown tree without following symlinks."""

    if not root.is_dir() or root.is_symlink():
        raise ScanError(f"invalid or symlinked directory: {root}")
    root = root.resolve(strict=True)
    if min(max_files, max_file_bytes, max_total_bytes) < 1:
        raise ScanError("scan bounds must be positive integers")

    paths: list[Path] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(current)
        dirnames.sort()
        filenames.sort()
        for dirname in tuple(dirnames):
            directory = base / dirname
            if directory.is_symlink():
                raise ScanError(
                    f"directory symlink is not allowed: {directory.relative_to(root)}"
                )
        for filename in filenames:
            path = base / filename
            if path.suffix.casefold() != ".md":
                continue
            if path.is_symlink():
                raise ScanError(
                    f"file symlink is not allowed: {path.relative_to(root)}"
                )
            paths.append(path)
            if len(paths) > max_files:
                raise ScanError(f"Markdown file count exceeds limit {max_files}")

    documents: list[Document] = []
    total_bytes = 0
    for path in sorted(paths):
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ScanError(f"cannot stat {path}: {exc}") from exc
        if size > max_file_bytes:
            raise ScanError(
                f"file exceeds {max_file_bytes} bytes: {path.relative_to(root)}"
            )
        total_bytes += size
        if total_bytes > max_total_bytes:
            raise ScanError(f"Markdown input exceeds {max_total_bytes} total bytes")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ScanError(f"cannot read UTF-8 Markdown {path}: {exc}") from exc
        documents.append(Document(path.relative_to(root), _tokens(text)))
    return documents


def find_overlaps(
    source: list[Document], target: list[Document], *, window: int
) -> list[Overlap]:
    """Return one deterministic location pair for each shared token window."""

    if window < 2:
        raise ScanError("window must be at least 2 tokens")

    source_windows: dict[tuple[str, ...], Path] = {}
    for document in source:
        for index in range(len(document.tokens) - window + 1):
            sequence = document.tokens[index : index + window]
            source_windows.setdefault(sequence, document.path)

    overlaps: dict[tuple[str, ...], Overlap] = {}
    for document in target:
        for index in range(len(document.tokens) - window + 1):
            sequence = document.tokens[index : index + window]
            source_path = source_windows.get(sequence)
            if source_path is None or sequence in overlaps:
                continue
            overlaps[sequence] = Overlap(
                phrase=" ".join(sequence),
                source_path=source_path,
                target_path=document.path,
            )
    return [overlaps[key] for key in sorted(overlaps)]


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find exact normalized token-window overlap in Markdown trees."
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--window", type=_positive_int, default=DEFAULT_WINDOW)
    parser.add_argument("--max-files", type=_positive_int, default=DEFAULT_MAX_FILES)
    parser.add_argument(
        "--max-file-bytes", type=_positive_int, default=DEFAULT_MAX_FILE_BYTES
    )
    parser.add_argument(
        "--max-total-bytes", type=_positive_int, default=DEFAULT_MAX_TOTAL_BYTES
    )
    parser.add_argument(
        "--max-reports", type=_positive_int, default=DEFAULT_MAX_REPORTS
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.window < 2:
        print("error: --window must be at least 2", file=sys.stderr)
        return 2
    try:
        source = scan_markdown(
            args.source,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )
        target = scan_markdown(
            args.target,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )
        overlaps = find_overlaps(source, target, window=args.window)
    except ScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not overlaps:
        print(
            f"no exact normalized {args.window}-token overlap across "
            f"{len(source)} source and {len(target)} target Markdown files"
        )
        return 0

    for overlap in overlaps[: args.max_reports]:
        print(
            f"{overlap.source_path} -> {overlap.target_path}: {overlap.phrase}",
            file=sys.stderr,
        )
    omitted = len(overlaps) - min(len(overlaps), args.max_reports)
    if omitted:
        print(f"... {omitted} additional distinct overlap(s) omitted", file=sys.stderr)
    print(
        f"found {len(overlaps)} distinct exact normalized "
        f"{args.window}-token overlap(s)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
