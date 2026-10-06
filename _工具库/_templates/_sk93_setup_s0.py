# -*- coding: utf-8 -*-
"""S0/S1 setup driver (U93, ASCII command line).
Creates <OUT>\\work, copies _toolkit *.py + the generic census template into it,
then runs _sk93_driver_s1unpack_census.py (unpack docx -> s1 meta -> s0_census.txt).
Chinese paths never travel through argv (U93); stdout stays ASCII (U90).
"""
import io
import os
import runpy
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _sk93_target as T

OUT = T.out()
WORK = os.path.join(OUT, "work")
TOOL = T.TOOLLIB
LOG = os.path.join(WORK, "_sk93_setup_log.txt")

os.makedirs(WORK, exist_ok=True)
copied, skipped = [], []
for f in sorted(os.listdir(TOOL)):
    if not f.endswith(".py"):
        continue
    dst = os.path.join(WORK, f)
    if os.path.exists(dst):
        skipped.append(f)
        continue
    shutil.copy2(os.path.join(TOOL, f), dst)
    copied.append(f)

cen_src = os.path.join(HERE, "_s0_census.py")
cen_dst = os.path.join(WORK, "s0_census.py")
shutil.copy2(cen_src, cen_dst)

lines = ["OUT_exists=%s" % os.path.isdir(OUT),
         "work=%s" % WORK,
         "copied=%d skipped=%d" % (len(copied), len(skipped)),
         "copied_list=%s" % ",".join(copied),
         "skipped_list=%s" % ",".join(skipped),
         "census=%s" % os.path.isfile(cen_dst)]
io.open(LOG, "w", encoding="utf-8").write("\n".join(lines))
print("SETUP_OK " + " ".join(l for l in lines[:1] + lines[2:5]))

runpy.run_path(os.path.join(HERE, "_sk93_driver_s1unpack_census.py"), run_name="__main__")
