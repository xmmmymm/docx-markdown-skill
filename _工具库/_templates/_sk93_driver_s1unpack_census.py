# -*- coding: utf-8 -*-
"""S1 unpack + S0 census driver (U93). Read the target path from _target.txt."""
import io
import json
import os
import runpy
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _sk93_target as T

DOCX = T.docx()
OUT = T.out()
WORK = os.path.join(OUT, "work")
UNP = os.path.join(WORK, "unpacked")
LOG = os.path.join(WORK, "_sk93_s0_log.txt")

log = []
assert os.path.isfile(DOCX), "docx missing: check _target.txt stem"
os.makedirs(UNP, exist_ok=True)
with zipfile.ZipFile(DOCX) as z:
    z.extractall(UNP)
media = os.path.join(UNP, "word", "media")
emb = os.path.join(UNP, "word", "embeddings")
log.append("media=%d" % (len(os.listdir(media)) if os.path.isdir(media) else 0))
log.append("embeddings=%d" % (len(os.listdir(emb)) if os.path.isdir(emb) else 0))
log.append("document.xml=%s" % os.path.isfile(os.path.join(UNP, "word", "document.xml")))

info = {
    "media": sorted(os.listdir(media)) if os.path.isdir(media) else [],
    "embeddings": sorted(os.listdir(emb)) if os.path.isdir(emb) else [],
    "relfiles": sorted(os.path.relpath(os.path.join(r, f), UNP)
                      for r, _, fs in os.walk(UNP) for f in fs if f.endswith(".rels")),
}
io.open(os.path.join(WORK, "s1_unpack_meta.json"), "w", encoding="utf-8").write(
    json.dumps(info, ensure_ascii=False, indent=1))

census = os.path.join(WORK, "s0_census.py")
if os.path.exists(census):
    runpy.run_path(census, run_name="__main__")
    log.append("census_txt=%s" % os.path.isfile(os.path.join(WORK, "s0_census.txt")))
else:
    log.append("census_skipped=no_s0_census_py_in_work")

io.open(LOG, "w", encoding="utf-8").write("\n".join(log))
print("UNPACK_OK " + " ".join(l for l in log if "=" in l))
