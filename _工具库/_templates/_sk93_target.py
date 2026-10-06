# -*- coding: utf-8 -*-
"""_sk93_target.py · U93 三要素取值器（skill 通用版，源自氮批同名取值器）

_target.txt 三要素（# 开头为注释行，取前 3 个非注释行）：
  第 1 行：输入文件夹（docx 所在，只扫第一层 .docx）
  第 2 行：输出根目录（成品将落 <输出根>/<stem>/）
  第 3 行：当前件 stem（docx 文件名去 .docx，**逐字照抄队列 json 的 stem**，含连续空格/全角字符）

环境变量 SKILL_TARGET 可整体覆盖：三要素按 \\t 分隔（ASCII 场景用）。
**命令行一律 ASCII（U93）**：中文路径只待在本文件 / _target.txt（UTF-8）里，绝不作 argv 直传。
"""
import os
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
TOOL = _here.parent            # _工具库
SKILLROOT = TOOL.parent        # 试题提取skill（skill 工程根）


def _lines():
    raw = os.environ.get("SKILL_TARGET", "")
    if raw:
        return [p for p in raw.split("\t") if p.strip()]
    txt = (_here / "_target.txt").read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in txt
            if ln.strip() and not ln.lstrip().startswith("#")]


_L = _lines()
if len(_L) < 3:
    sys.stderr.write("BAD _target.txt: need 3 non-comment lines "
                     "(input / output-root / stem)\n")
    sys.exit(2)

IN_ROOT = Path(_L[0])
OUT_ROOT = Path(_L[1])
STEM = _L[2]

# 兼容旧模板的模块级属性名（源自氮批同名取值器；setup_s0 等模板在用）
TOOLLIB = TOOL            # = _工具库 目录（与 tool() 同源，永远指母本库）
BATCHROOT = IN_ROOT       # 旧语义「docx 所在目录」＝skill 的输入夹


def in_root():
    """输入文件夹（docx 所在）"""
    return IN_ROOT


def out_root():
    """输出根目录"""
    return OUT_ROOT


def stem():
    """当前件 stem（str，逐字照抄队列 json）"""
    return STEM


def out():
    """本件输出目录：<输出根>/<stem>/"""
    return OUT_ROOT / STEM


def work():
    """本件 work 目录：<输出根>/<stem>/work/"""
    return out() / "work"


def docx():
    """源 docx：<输入文件夹>/<stem>.docx"""
    return IN_ROOT / (STEM + ".docx")


def tool(name=None):
    """_工具库 目录（或其中脚本：tool("audit.py")）；
    脚本被拷进 work\\ 后本函数仍指向 _工具库\\（与氮批口径一致：tool() 永远指母本库）"""
    return TOOL / name if name else TOOL


# 注：以下三个取值器是**对外 API**，供各驱动脚本 import 调用，
# 库内自身不引用它们 ⇒ 静态体检（_audit_static.py）会把它们报成"定义未用"，
# 属**预期误报**，勿删（删了驱动脚本会 AttributeError）。
def skillroot():
    """skill 工程根（_skill规划.md、_队列\\ 等所在）"""
    return SKILLROOT


def queue_dir():
    """批次队列目录：<skill根>/_队列/"""
    return SKILLROOT / "_队列"


# 兼容别名：旧模板中 BATCHROOT 的语义＝「docx 所在目录」
def batchroot():
    return IN_ROOT


if __name__ == "__main__":
    # 自检（stdout 仅 ASCII，U2/U90）
    print("IN_ROOT  exists=%s" % IN_ROOT.exists())
    print("OUT_ROOT exists=%s" % OUT_ROOT.exists())
    print("DOCX     exists=%s" % docx().exists())
    print("OUT      exists=%s" % out().exists())
    print("STEM     len=%d spaces=%d u3000=%d" % (
        len(STEM), STEM.count(" "), STEM.count("　")))
