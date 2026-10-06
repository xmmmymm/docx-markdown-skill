# -*- coding: utf-8 -*-
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sk93_target as T

OUT = T.out()
sys.argv = ["_sk_imgprep.py", OUT, "--grid", "84x30", "--src", "media"]
local = os.path.join(OUT, "work", "_sk_imgprep.py")
runpy.run_path(local if os.path.exists(local) else T.tool("_sk_imgprep.py"), run_name="__main__")
