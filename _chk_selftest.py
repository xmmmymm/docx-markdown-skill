# -*- coding: utf-8 -*-
"""_chk_selftest.py · 工程一键体检（把分散的门禁收成一条命令，exit 0=全绿）。

背景：本工程的流程纪律要求改 CORE 前跑「编译自检 + 基线比对 + 提示词一致性 +
脱敏自查 + 冒烟」，但此前分散在多个脚本、靠人记。本脚本把它们串起来，
任何一项失败即以非零退出，便于人工与自动化共用。

检查项（stdout 仅 ASCII，U2/U90）：
  1 compile        全部 *.py 语法编译通过
  2 baseline       _sk0_baseline.py 报 CHANGED=0 MISSING=0（指纹未漂移）
  3 prompt-drift   _启动提示词.md 与 _skill规划.md §10 逐字一致
  4 local-paths    入库文件不含本机绝对路径
  5 balance-smoke  _sk_balance.py 对合成语料判对（守恒 0 bad / 不守恒 1 bad）
  6 info-roundtrip _sk_info.py 在临时输入夹 init→check 全链路可用（env 模式，不碰真数据）

用法：<py> _chk_selftest.py [--verbose]
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOL = ROOT / "_工具库"
TPL = TOOL / "_templates"
PY = sys.executable
VERBOSE = "--verbose" in sys.argv
SKIP_DIRS = {"__pycache__", ".git", "_题库"}


def run(script, args=(), env=None, cwd=None):
    """跑一个脚本，返回 (rc, 合并输出)。输出按 UTF-8 解码，失败也不抛。"""
    p = subprocess.run([PY, str(script)] + [str(a) for a in args],
                       capture_output=True, env=env, cwd=str(cwd or script.parent))
    out = (p.stdout or b"").decode("utf-8", "replace") + \
          (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, out.strip()


def py_files():
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in sorted(fns):
            if f.endswith(".py"):
                yield Path(dp) / f


def check_compile():
    bad = []
    n = 0
    for f in py_files():
        n += 1
        p = subprocess.run([PY, "-m", "py_compile", str(f)], capture_output=True)
        if p.returncode != 0:
            bad.append(f.name)
    if bad:
        return False, "files=%d FAIL=%s" % (n, ",".join(bad[:5]))
    return True, "files=%d all compiled" % n


def check_baseline():
    rc, out = run(TOOL / "_sk0_baseline.py")
    line = out.splitlines()[-1] if out else ""
    ok = rc == 0 and "CHANGED=0" in line and "MISSING=0" in line
    return ok, line or "no output"


def check_prompt_drift():
    rc, out = run(ROOT / "_chk_prompt_drift.py")
    return (rc == 0 and out.startswith("IDENTICAL")), (out.splitlines() or [""])[0]


def check_local_paths():
    rc, out = run(ROOT / "_chk_no_local_paths.py")
    return (rc == 0 and "HITS=0" in out), (out.splitlines() or [""])[-1]


def check_balance():
    """合成语料：A 守恒、B 不守恒 ⇒ 期望 eq=2 bad=1。"""
    tmp = Path(tempfile.mkdtemp(prefix="_sk_bal_"))
    try:
        md = tmp / "probe.md"
        md.write_text("1. choose\nA. H2+Cl2=2HCl\nB. H2+Cl2=HCl\n", encoding="utf-8")
        rc, out = run(TOOL / "_sk_balance.py", [md])
        last = out.splitlines()[-1] if out else ""
        ok = rc == 0 and "eq=2" in last and "bad=1" in last
        return ok, last or "no output"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_info_roundtrip():
    """临时输入夹 + SKILL_TARGET env：init 建表、check 应 exit 0。不触碰真实输入夹。"""
    tmp = Path(tempfile.mkdtemp(prefix="_sk_info_"))
    try:
        (tmp / "demo-lesson.docx").write_bytes(b"x" * 2048)
        env = dict(os.environ)
        env["SKILL_TARGET"] = "%s\t%s\t" % (tmp, tmp)
        rc1, o1 = run(TOOL / "_sk_info.py", ["init"], env=env)
        rc2, o2 = run(TOOL / "_sk_info.py", ["check"], env=env)
        table = tmp / "_提取信息.md"
        ok = rc1 == 0 and rc2 == 0 and table.is_file()
        return ok, "init=%d check=%d table=%s" % (rc1, rc2, "yes" if table.is_file() else "no")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


CHECKS = [
    ("1 compile", check_compile),
    ("2 baseline", check_baseline),
    ("3 prompt-drift", check_prompt_drift),
    ("4 local-paths", check_local_paths),
    ("5 balance-smoke", check_balance),
    ("6 info-roundtrip", check_info_roundtrip),
]


def main():
    print("== _chk_selftest ==  root=%s" % ROOT.name)
    fails = 0
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:                      # 体检器自身异常也算失败
            ok, detail = False, "EXC %s: %s" % (e.__class__.__name__, e)
        print("%-18s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        if not ok:
            fails += 1
    print("RESULT=%s  passed=%d/%d" % ("ALL GREEN" if not fails else "FAILED",
                                       len(CHECKS) - fails, len(CHECKS)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())