import ast
import json
import os
import sys
import trace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TARGET_FILES = {
    "src/core/event_bus.py",
    "src/plugins/manager.py",
    "src/ui/island_window.py",
    "src/ui/shortcut_dots.py",
    "src/utils/config.py",
}


def executable_lines(path: Path) -> set[int]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and hasattr(node, "lineno"):
            lines.add(node.lineno)
    return lines


def main():
    tracer = trace.Trace(count=True, trace=False)
    code = tracer.runfunc(pytest.main, ["-q", str(ROOT / "tests")])
    result = tracer.results()
    counts = result.counts
    covered_total = 0
    executable_total = 0
    details = {}
    for file_path in SRC.rglob("*.py"):
        rel = str(file_path.relative_to(ROOT)).replace("\\", "/")
        if rel not in TARGET_FILES:
            continue
        exec_lines = executable_lines(file_path)
        hit_lines = {line for (path, line), count in counts.items() if Path(path).resolve() == file_path.resolve() and count > 0}
        covered = len(exec_lines & hit_lines)
        total = len(exec_lines)
        covered_total += covered
        executable_total += total
        details[rel] = {"covered": covered, "total": total}
    coverage = round((covered_total / executable_total) * 100, 2) if executable_total else 0.0
    payload = {
        "coverage": coverage,
        "covered_lines": covered_total,
        "executable_lines": executable_total,
        "details": details,
        "pytest_exit": code,
    }
    report_json = ROOT / "docs" / "Coverage_Report.json"
    report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md = ROOT / "docs" / "Test_Report.md"
    report_md.write_text(
        f"# 测试报告\n\n- 单元测试退出码: {code}\n- 覆盖率: {coverage}%\n- 覆盖行数: {covered_total}/{executable_total}\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if code == 0 and coverage >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
