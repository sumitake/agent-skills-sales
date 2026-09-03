#!/usr/bin/env python3
"""Report exact normalized prose-window overlap between two Markdown trees.

This is a bounded accidental-copying screen, not a legal conclusion. It never
executes content from either tree.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


DEFAULT_WINDOW = 12
DEFAULT_MAX_ENTRIES = 2_000
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_TOKENS = 500_000
DEFAULT_MAX_REPORTS = 100
MAX_WINDOW = 64
DIGEST_SIZE = 16
LOCATION_SHIFT = 32
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


@dataclass(frozen=True)
class OverlapResult:
    samples: tuple[Overlap, ...]
    total: int


def _tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(TOKEN_RE.findall(normalized))


def _markdown_paths(root: Path, *, max_entries: int) -> list[Path]:
    """Return deterministic Markdown paths from a fail-closed bounded walk."""

    pending = [root]
    paths: list[Path] = []
    encountered = 0
    while pending:
        directory = pending.pop()
        children: list[tuple[str, Path, bool, bool]] = []
        try:
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    encountered += 1
                    if encountered > max_entries:
                        raise ScanError(
                            f"input tree exceeds {max_entries} traversed entries"
                        )
                    path = Path(entry.path)
                    try:
                        if entry.is_symlink():
                            raise ScanError(
                                "symlink is not allowed: "
                                f"{path.relative_to(root)}"
                            )
                        is_directory = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError as exc:
                        raise ScanError(
                            f"cannot inspect {path.relative_to(root)}: {exc}"
                        ) from exc
                    children.append((entry.name, path, is_directory, is_file))
        except OSError as exc:
            raise ScanError(
                f"cannot scan directory {directory.relative_to(root)}: {exc}"
            ) from exc

        directories: list[Path] = []
        for name, path, is_directory, is_file in sorted(children):
            if is_directory:
                if name != ".git":
                    directories.append(path)
            elif is_file and path.suffix.casefold() == ".md":
                paths.append(path)
        pending.extend(reversed(directories))
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def scan_markdown(
    root: Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[Document]:
    """Read a bounded Markdown tree without following symlinks."""

    if not root.is_dir() or root.is_symlink():
        raise ScanError(f"invalid or symlinked directory: {root}")
    root = root.resolve(strict=True)
    if min(max_entries, max_file_bytes, max_total_bytes, max_tokens) < 1:
        raise ScanError("scan bounds must be positive integers")

    paths = _markdown_paths(root, max_entries=max_entries)

    documents: list[Document] = []
    total_bytes = 0
    total_tokens = 0
    for path in paths:
        try:
            with path.open("rb") as handle:
                payload = handle.read(max_file_bytes + 1)
        except OSError as exc:
            raise ScanError(f"cannot read Markdown {path}: {exc}") from exc
        if len(payload) > max_file_bytes:
            raise ScanError(
                f"file exceeds {max_file_bytes} bytes: {path.relative_to(root)}"
            )
        total_bytes += len(payload)
        if total_bytes > max_total_bytes:
            raise ScanError(f"Markdown input exceeds {max_total_bytes} total bytes")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ScanError(f"cannot decode UTF-8 Markdown {path}: {exc}") from exc
        tokens = _tokens(text)
        total_tokens += len(tokens)
        if total_tokens > max_tokens:
            raise ScanError(f"Markdown input exceeds {max_tokens} normalized tokens")
        documents.append(Document(path.relative_to(root), tokens))
    return documents


def _window_digest(tokens: tuple[str, ...], start: int, window: int) -> bytes:
    digest = hashlib.blake2b(digest_size=DIGEST_SIZE, person=b"sales-overlap")
    for token in tokens[start : start + window]:
        encoded = token.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.digest()


def _pack_location(document_index: int, token_index: int) -> int:
    if document_index >= 1 << LOCATION_SHIFT or token_index >= 1 << LOCATION_SHIFT:
        raise ScanError("document or token index exceeds packed-location limit")
    return ((document_index << LOCATION_SHIFT) | token_index) + 1


def _unpack_location(packed: int) -> tuple[int, int]:
    value = abs(packed) - 1
    return value >> LOCATION_SHIFT, value & ((1 << LOCATION_SHIFT) - 1)


def _same_window(
    documents: list[Document],
    packed: int,
    candidate: tuple[str, ...],
    candidate_start: int,
    window: int,
) -> bool:
    document_index, token_index = _unpack_location(packed)
    source_tokens = documents[document_index].tokens
    return source_tokens[token_index : token_index + window] == candidate[
        candidate_start : candidate_start + window
    ]


def find_overlaps(
    source: list[Document],
    target: list[Document],
    *,
    window: int,
    max_reports: int = DEFAULT_MAX_REPORTS,
) -> OverlapResult:
    """Count distinct overlaps and retain bounded deterministic samples."""

    if not 2 <= window <= MAX_WINDOW:
        raise ScanError(f"window must be between 2 and {MAX_WINDOW} tokens")
    if max_reports < 1:
        raise ScanError("max_reports must be positive")

    source_windows: dict[bytes, int | list[int]] = {}
    for document_index, document in enumerate(source):
        for index in range(len(document.tokens) - window + 1):
            key = _window_digest(document.tokens, index, window)
            packed = _pack_location(document_index, index)
            existing = source_windows.get(key)
            if existing is None:
                source_windows[key] = packed
                continue
            if isinstance(existing, int):
                if not _same_window(
                    source, existing, document.tokens, index, window
                ):
                    source_windows[key] = [existing, packed]
                continue
            if not any(
                _same_window(source, location, document.tokens, index, window)
                for location in existing
            ):
                existing.append(packed)

    samples: list[Overlap] = []
    total = 0
    for document in target:
        for index in range(len(document.tokens) - window + 1):
            key = _window_digest(document.tokens, index, window)
            existing = source_windows.get(key)
            if existing is None:
                continue
            locations = [existing] if isinstance(existing, int) else existing
            for offset, packed in enumerate(locations):
                if not _same_window(source, packed, document.tokens, index, window):
                    continue
                if packed < 0:
                    break
                total += 1
                if len(samples) < max_reports:
                    source_document, _ = _unpack_location(packed)
                    samples.append(
                        Overlap(
                            phrase=" ".join(
                                document.tokens[index : index + window]
                            ),
                            source_path=source[source_document].path,
                            target_path=document.path,
                        )
                    )
                if isinstance(existing, int):
                    source_windows[key] = -packed
                else:
                    existing[offset] = -packed
                break
    return OverlapResult(tuple(samples), total)


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
    parser.add_argument(
        "--max-entries",
        "--max-files",
        dest="max_entries",
        type=_positive_int,
        default=DEFAULT_MAX_ENTRIES,
        help="maximum traversed entries per input tree (--max-files is an alias)",
    )
    parser.add_argument(
        "--max-file-bytes", type=_positive_int, default=DEFAULT_MAX_FILE_BYTES
    )
    parser.add_argument(
        "--max-total-bytes", type=_positive_int, default=DEFAULT_MAX_TOTAL_BYTES
    )
    parser.add_argument(
        "--max-tokens", type=_positive_int, default=DEFAULT_MAX_TOKENS
    )
    parser.add_argument(
        "--max-reports", type=_positive_int, default=DEFAULT_MAX_REPORTS
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 2 <= args.window <= MAX_WINDOW:
        print(
            f"error: --window must be between 2 and {MAX_WINDOW}",
            file=sys.stderr,
        )
        return 2
    try:
        source = scan_markdown(
            args.source,
            max_entries=args.max_entries,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
            max_tokens=args.max_tokens,
        )
        target = scan_markdown(
            args.target,
            max_entries=args.max_entries,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
            max_tokens=args.max_tokens,
        )
        overlaps = find_overlaps(
            source, target, window=args.window, max_reports=args.max_reports
        )
    except ScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not overlaps.total:
        print(
            f"no exact normalized {args.window}-token overlap across "
            f"{len(source)} source and {len(target)} target Markdown files"
        )
        return 0

    for overlap in overlaps.samples:
        print(
            f"{overlap.source_path} -> {overlap.target_path}: {overlap.phrase}",
            file=sys.stderr,
        )
    omitted = overlaps.total - len(overlaps.samples)
    if omitted:
        print(f"... {omitted} additional distinct overlap(s) omitted", file=sys.stderr)
    print(
        f"found {overlaps.total} distinct exact normalized "
        f"{args.window}-token overlap(s)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
