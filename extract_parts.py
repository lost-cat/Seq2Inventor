#!/usr/bin/env python3
"""
Extract Inventor part files from archives and directories.

- Recursively scans a source folder (default: data/inventor_parts)
- Extracts supported archives (zip, tar, tar.gz, tgz, tar.bz2, tbz2) to a temp folder under the source
- Finds all .ipt files (case-insensitive) from both the extracted content and regular subdirectories
- Copies them into a flat destination folder (default: data/parts), adding suffixes to avoid name collisions

Usage (PowerShell):
    python extract_parts.py --src data/inventor_parts --dst data/parts

Options:
    --clean-extracted       Remove the temporary extracted folder after finishing
    --dry-run               Show what would happen without making changes
    --also-scan-dirs        Also scan non-archive directories under --src for *.ipt (default: true); use --no-also-scan-dirs to disable
    --seq-start N           Starting index for sequential naming (default: next available based on existing files)
    --seq-width W           Zero-padding width for filenames like 0001.ipt (default: 4)

Notes:
- Only stdlib archive formats are supported. 7z/rar are skipped with a warning.
- Destination file naming: <archive_stem>__<file_stem>[__N].ipt to avoid collisions. For files from non-archive dirs, <dir_stem>__<file_stem>[__N].ipt.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
import re
from typing import Iterable, Iterator, List, Optional, Tuple

SUPPORTED_ARCHIVE_EXTS = {
    ".zip",
    ".tar",
    ".tgz",
    ".tar.gz",
    ".tbz2",
    ".tar.bz2",
}

UNSUPPORTED_ARCHIVE_HINTS = {
    ".7z": "7z archives are not supported by the Python standard library. Consider installing 'py7zr' and adding custom handling.",
    ".rar": "RAR archives are not supported by the Python standard library. Consider installing 'rarfile' and WinRAR/UnRAR and adding custom handling.",
}


def is_supported_archive(path: Path) -> bool:
    lower = path.name.lower()
    return any(lower.endswith(ext) for ext in SUPPORTED_ARCHIVE_EXTS)


def is_known_unsupported_archive(path: Path) -> Optional[str]:
    lower = path.name.lower()
    for ext, msg in UNSUPPORTED_ARCHIVE_HINTS.items():
        if lower.endswith(ext):
            return msg
    return None


def iter_files_recursive(root: Path) -> Iterator[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            yield Path(dirpath) / fn


def safe_mkdir(path: Path, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[dry-run] mkdir -p {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)


def extract_archive(archive: Path, dest_dir: Path, dry_run: bool = False) -> Optional[Path]:
    """Extract a supported archive into a dedicated subfolder and return the folder path.
    Returns None if skipped or failed.
    """
    # Choose subdir name based on archive stem(s)
    subdir_name = archive.name
    for suffix in (".tar.gz", ".tar.bz2", ".zip", ".tgz", ".tbz2", ".tar"):
        if subdir_name.lower().endswith(suffix):
            subdir_name = subdir_name[: -len(suffix)]
            break
    extract_to = dest_dir / subdir_name
    safe_mkdir(extract_to, dry_run=dry_run)

    if dry_run:
        print(f"[dry-run] Would extract: {archive} -> {extract_to}")
        return extract_to

    try:
        if archive.name.lower().endswith(".zip"):
            with zipfile.ZipFile(archive, 'r') as zf:
                zf.extractall(extract_to)
        elif archive.name.lower().endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2")):
            mode = 'r'
            lower = archive.name.lower()
            if lower.endswith(('.tar.gz', '.tgz')):
                mode = 'r:gz'
            elif lower.endswith(('.tar.bz2', '.tbz2')):
                mode = 'r:bz2'
            with tarfile.open(archive, mode) as tf:
                tf.extractall(extract_to)
        else:
            print(f"[warn] Unsupported archive format (should not happen here): {archive}")
            return None
    except Exception as e:
        print(f"[error] Failed to extract {archive}: {e}")
        return None

    return extract_to


def find_ipt_files(roots: Iterable[Path]) -> Iterator[Tuple[Path, Path]]:
    """Yield (root, ipt_path) for every .ipt file found recursively under each root.
    The 'root' helps determine origin for naming.
    """
    for root in roots:
        for p in iter_files_recursive(root):
            if p.suffix.lower() == ".ipt":
                yield (root, p)


def next_seq_dest(dest_dir: Path, used_names: set[str], seq: int, width: int) -> Tuple[Path, int]:
    """Return (next_available_path, next_seq_value). Ensures case-insensitive uniqueness on Windows."""
    while True:
        name = f"{seq:0{width}d}.ipt"
        candidate = dest_dir / name
        if candidate.name.lower() not in used_names:
            used_names.add(candidate.name.lower())
            return candidate, seq + 1
        seq += 1


def copy_to_seq(ipt_path: Path, dest_path: Path, dry_run: bool = False) -> Optional[Path]:
    if dry_run:
        print(f"[dry-run] copy {ipt_path} -> {dest_path}")
        return dest_path
    try:
        shutil.copy2(ipt_path, dest_path)
        return dest_path
    except Exception as e:
        print(f"[error] Failed to copy {ipt_path} -> {dest_path}: {e}")
        return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract and collect Inventor .ipt files from archives and directories.")
    parser.add_argument("--src", type=str, default=str(Path("data") / "inventor_parts"), help="Source root folder to scan (default: data/inventor_parts)")
    parser.add_argument("--dst", type=str, default=str(Path("data") / "parts"), help="Destination folder for collected .ipt files (default: data/parts)")
    parser.add_argument("--clean-extracted", action="store_true", help="Delete temporary extracted content after copying")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions without writing files")
    parser.add_argument("--also-scan-dirs", dest="also_scan_dirs", action=argparse.BooleanOptionalAction, default=True, help="Also scan non-archive directories in --src for .ipt files (default: enabled)")
    parser.add_argument("--seq-start", type=int, default=None, help="Starting index for sequential filenames (default: infer from existing)")
    parser.add_argument("--seq-width", type=int, default=4, help="Zero-padding width for sequential filenames (default: 4)")

    args = parser.parse_args(argv)

    src_root = Path(args.src).resolve()
    dst_root = Path(args.dst).resolve()
    extracted_root = src_root / "_extracted"

    if not src_root.exists():
        print(f"[error] Source folder does not exist: {src_root}")
        return 2

    safe_mkdir(dst_root, dry_run=args.dry_run)
    safe_mkdir(extracted_root, dry_run=args.dry_run)

    # 1) Scan for archives and extract
    archives: List[Path] = []
    unsupported: List[Tuple[Path, str]] = []
    for f in iter_files_recursive(src_root):
        # Do not treat files under the _extracted folder as inputs
        try:
            f.relative_to(extracted_root)
            # If relative_to doesn't raise, it's under extracted root; skip
            continue
        except ValueError:
            pass

        if is_supported_archive(f):
            archives.append(f)
        else:
            hint = is_known_unsupported_archive(f)
            if hint:
                unsupported.append((f, hint))

    if unsupported:
        print("[info] Skipping unsupported archives:")
        for path, msg in unsupported:
            print(f"  - {path}: {msg}")

    extracted_dirs: List[Path] = []
    for a in archives:
        out_dir = extract_archive(a, extracted_root, dry_run=args.dry_run)
        if out_dir is not None:
            extracted_dirs.append(out_dir)

    # 2) Gather IPT files
    search_roots: List[Path] = []
    if args.also_scan_dirs:
        search_roots.append(src_root)
    search_roots.extend(extracted_dirs)

    ipt_candidates = list(find_ipt_files(search_roots))
    if not ipt_candidates:
        print("[warn] No .ipt files found.")
    else:
        print(f"[info] Found {len(ipt_candidates)} .ipt files to collect.")

    # 3) Copy with sequential naming
    existing_names = {p.name.lower() for p in dst_root.glob('*.ipt')} if dst_root.exists() else set()

    # Determine starting seq index
    def infer_next_seq_from_existing(names: set[str]) -> int:
        max_idx = -1
        pat = re.compile(r"^(\d+)\.ipt$")
        for name in names:
            m = pat.match(name)
            if m:
                try:
                    val = int(m.group(1))
                    if val > max_idx:
                        max_idx = val
                except ValueError:
                    pass
        return max_idx + 1

    seq = args.seq_start if args.seq_start is not None else infer_next_seq_from_existing(existing_names)
    width = max(1, int(args.seq_width))

    used_names: set[str] = set(existing_names)

    copied = 0
    for _root, ipt_path in ipt_candidates:
        dest_path, seq = next_seq_dest(dst_root, used_names, seq, width)
        dest = copy_to_seq(ipt_path, dest_path, dry_run=args.dry_run)
        if dest is not None:
            copied += 1

    print(f"[done] Collected {copied} .ipt files into {dst_root}")

    # 4) Optionally clean extracted folder
    if args.clean_extracted and extracted_root.exists() and not args.dry_run:
        try:
            shutil.rmtree(extracted_root)
            print(f"[info] Removed extracted content: {extracted_root}")
        except Exception as e:
            print(f"[warn] Failed to remove extracted folder {extracted_root}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
