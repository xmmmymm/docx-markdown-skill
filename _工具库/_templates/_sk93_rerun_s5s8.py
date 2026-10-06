# -*- coding: utf-8 -*-
"""Re-run S5-S8 after a source-level edit (U52/U94). Read target from _target.txt."""
import io
import os
import runpy
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sk93_target as T

WORK = T.work()
LOG = os.path.join(WORK, "_sk93_rerun_log.txt")
STEPS = ["make_skeleton.py", "make_md.py", "copy_images.py", "audit.py", "fix_fullwidth.py"]

lines = []
for name in STEPS:
    path = os.path.join(WORK, name)
    lines.append("==== RUN %s ====" % name)
    if not os.path.exists(path):
        lines.append("SKIP missing")
        continue
    try:
        runpy.run_path(path, run_name="__main__")
        lines.append("exit=ok")
    except SystemExit as e:
        lines.append("SystemExit=%s" % e.code)
    except Exception:
        lines.append(traceback.format_exc())
io.open(LOG, "w", encoding="utf-8").write("\n".join(lines))
print("RERUN_LOG_WRITTEN steps=%d" % len(STEPS))
