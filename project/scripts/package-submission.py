# -*- coding: utf-8 -*-
"""Package submission ZIP per 实训要求 Section 5."""

import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT / "project"
MEMBERS = "曾露-伍灵晰-吴芝"
OUT_DIR = REPO_ROOT / "submission-package"
ZIP_PATH = REPO_ROOT / f"{MEMBERS}-综合测试实践.zip"

EXCLUDE_DIRS = {"venv", "__pycache__", ".pytest_cache", "htmlcov", "instance", "tests", ".git"}
EXCLUDE_FILES = {".env", ".coverage"}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix == ".pyc":
        return True
    return False


def copy_tree(src: Path, dst: Path):
    for item in src.rglob("*"):
        if should_skip(item.relative_to(src)):
            continue
        rel = item.relative_to(src)
        if any(p in EXCLUDE_DIRS for p in rel.parts):
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir()

    # project/ (backend + frontend, no tests/)
    copy_tree(PROJECT_ROOT, OUT_DIR / "project")

    # tests/ with required folder names
    tests_root = OUT_DIR / "tests"
    mapping = {
        "unit": "unit_tests",
        "api": "api_tests",
        "auto": "auto_tests",
        "performance": "performance_tests",
    }
    for src_name, dst_name in mapping.items():
        src = PROJECT_ROOT / "tests" / src_name
        dst = tests_root / dst_name
        if src.exists():
            copy_tree(src, dst)
    conftest = PROJECT_ROOT / "tests" / "conftest.py"
    if conftest.exists():
        shutil.copy2(conftest, tests_root / "conftest.py")

    # docx at root
    for suffix in ["综合测试计划", "综合测试报告"]:
        docx = REPO_ROOT / f"{MEMBERS}-{suffix}.docx"
        if docx.exists():
            shutil.copy2(docx, OUT_DIR / docx.name)
        else:
            print(f"WARNING: missing {docx}")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    inner_root = f"{MEMBERS}-综合测试实践"
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in OUT_DIR.rglob("*"):
            if f.is_file():
                arcname = Path(inner_root) / f.relative_to(OUT_DIR)
                zf.write(f, arcname.as_posix())

    print(f"Created: {ZIP_PATH}")
    print("Contents:")
    for p in sorted(OUT_DIR.rglob("*")):
        if p.is_dir():
            continue
        print(f"  {p.relative_to(OUT_DIR)}")


if __name__ == "__main__":
    main()
