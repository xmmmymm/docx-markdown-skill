# -*- coding: utf-8 -*-
"""看门狗驱动（U93：输出目录取自 _target.txt，命令行全 ASCII）。
用法（在 _templates 目录内，相对 ASCII 名运行）：
    & $py _sk93_watchdog.py                       # 用下方安全默认值
    & $py _sk93_watchdog.py --interval 120 --times 25 --stall 5
⚠ 默认值由「间隔 60 / 次数 20 / 连续 2 次零增长」调整为「120 / 20 / 4」：
  序2 实测**看门狗先于子代理首写启动**时会误报 STALLED(no_progress x2) ——
  子代理开工前须读 7 份控制文件（只读阶段可达 10 分钟以上，期间磁盘零增长属正常）。
  ⇒ 宽限期须 ≥ interval×stall ≈ 8 分钟，否则会把"只读阶段"误判为停摆并触发无谓换棒。
"""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sk93_target as T

DEFAULTS = ["--interval", "120", "--times", "40", "--stall", "4"]
extra = [a for a in sys.argv[1:]]
flags = extra if any(a.startswith("--") for a in extra) else DEFAULTS
sys.argv = ["_sk_watchdog.py", T.out()] + flags
runpy.run_path(T.tool("_sk_watchdog.py"), run_name="__main__")
