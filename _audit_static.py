# -*- coding: utf-8 -*-
"""_audit_static.py · 工程静态体检（stdout 仅 ASCII）。

检查项：
  1 未使用的 import
  2 定义但从未被引用的模块级常量 / 函数（同工程内全局搜索）
  3 裸 except / except Exception 后静默 pass
  4 可疑：文件读写未指定 encoding
  5 同名函数跨文件重复定义（可能是复制粘贴漂移）
  6 TODO / FIXME / XXX 标记
用法：<py> _audit_static.py [根目录]
"""
import ast
import io
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

SKIP = {"__pycache__", ".git", "_题库"}
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()


def py_files():
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP]
        for f in sorted(fns):
            if f.endswith(".py"):
                yield Path(dp) / f


def main():
    files = list(py_files())
    srcs = {}
    for f in files:
        try:
            srcs[f] = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            print("UNREADABLE %s" % f.relative_to(ROOT))
    print("SCANNED=%d" % len(srcs))

    # ── 1 未使用 import ──────────────────────────────────────────
    print("\n== 1. 未使用的 import ==")
    n1 = 0
    for f, s in srcs.items():
        try:
            tree = ast.parse(s)
        except SyntaxError as e:
            print("  SYNTAX %s: %s" % (f.name, e))
            continue
        imported = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported[(a.asname or a.name.split(".")[0])] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name != "*":
                        imported[(a.asname or a.name)] = node.lineno
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                pass
        # 属性访问的根名字
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                cur = node
                while isinstance(cur, ast.Attribute):
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    used.add(cur.id)
        for name, ln in sorted(imported.items(), key=lambda x: x[1]):
            if name not in used and name not in s.split("import", 1)[0]:
                # 再宽松核一次：整词出现在源码里（含字符串/注释）就算用到
                if not re.search(r"\b%s\b" % re.escape(name), s):
                    print("  %s:%d  %s" % (f.relative_to(ROOT), ln, name))
                    n1 += 1
    print("  TOTAL=%d" % n1)

    # ── 2 定义但从未被引用 ──────────────────────────────────────
    print("\n== 2. 定义但从未被引用的模块级符号 ==")
    allsrc = "\n".join(srcs.values())
    n2 = 0
    for f, s in srcs.items():
        try:
            tree = ast.parse(s)
        except SyntaxError:
            continue
        for node in tree.body:
            names = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for nm in names:
                if nm.startswith("__") or nm in ("main",):
                    continue
                # 全工程出现次数（定义处 1 次）
                cnt = len(re.findall(r"\b%s\b" % re.escape(nm), allsrc))
                if cnt <= 1:
                    kind = "func" if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else "const"
                    print("  [%s] %s:%d  %s" % (kind, f.relative_to(ROOT), node.lineno, nm))
                    n2 += 1
    print("  TOTAL=%d" % n2)

    # ── 3 裸 except / 静默 pass ─────────────────────────────────
    print("\n== 3. 裸 except / 静默吞异常 ==")
    n3 = 0
    for f, s in srcs.items():
        try:
            tree = ast.parse(s)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    print("  BARE  %s:%d" % (f.relative_to(ROOT), node.lineno))
                    n3 += 1
                elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    print("  PASS  %s:%d" % (f.relative_to(ROOT), node.lineno))
                    n3 += 1
    print("  TOTAL=%d" % n3)

    # ── 4 文件读写未指定 encoding ───────────────────────────────
    print("\n== 4. 文本读写未显式指定 encoding ==")
    n4 = 0
    for f, s in srcs.items():
        try:
            tree = ast.parse(s)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                nm = fn.attr if isinstance(fn, ast.Attribute) else (
                    fn.id if isinstance(fn, ast.Name) else "")
                if nm in ("open", "read_text", "write_text"):
                    kws = {k.arg for k in node.keywords}
                    if "encoding" not in kws and "b" not in (getattr(node.args[1], "value", "")
                                                             if len(node.args) > 1 else ""):
                        print("  %s:%d  %s(...)" % (f.relative_to(ROOT), node.lineno, nm))
                        n4 += 1
    print("  TOTAL=%d" % n4)

    # ── 5 跨文件同名函数 ────────────────────────────────────────
    print("\n== 5. 跨文件同名函数（≥3 处，疑似复制粘贴） ==")
    defs = defaultdict(list)
    for f, s in srcs.items():
        try:
            tree = ast.parse(s)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs[node.name].append(f.relative_to(ROOT))
    n5 = 0
    for nm, fs in sorted(defs.items()):
        if len(fs) >= 3:
            print("  %-18s x%d  %s" % (nm, len(fs), ", ".join(str(x) for x in fs[:5])))
            n5 += 1
    print("  TOTAL=%d" % n5)

    # ── 6 标记 ──────────────────────────────────────────────────
    print("\n== 6. TODO / FIXME / XXX / 桩 ==")
    n6 = 0
    for f, s in srcs.items():
        for i, ln in enumerate(s.splitlines(), 1):
            if re.search(r"TODO|FIXME|XXX|HACK|桩|待实现|未实现", ln):
                print("  %s:%d  %s" % (f.relative_to(ROOT), i, ln.strip()[:78]))
                n6 += 1
    print("  TOTAL=%d" % n6)

    print("\nSUMMARY unused_import=%d unreferenced=%d except=%d no_encoding=%d dupfunc=%d markers=%d"
          % (n1, n2, n3, n4, n5, n6))
    return 0


if __name__ == "__main__":
    sys.exit(main())