# -*- coding: utf-8 -*-
"""S1: docx -> work/unpacked/ ；打印 ASCII 摘要"""
import sys, zipfile, re, json
from pathlib import Path

docx = Path(sys.argv[1])
BASE = Path(__file__).resolve().parent
UNP = BASE / "unpacked"
UNP.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(docx) as z:
    z.extractall(UNP)

media = sorted(p.name for p in (UNP / "word/media").iterdir()) if (UNP / "word/media").is_dir() else []
emb = sorted(p.name for p in (UNP / "word/embeddings").iterdir()) if (UNP / "word/embeddings").is_dir() else []
xmls = sorted(str(p.relative_to(UNP)) for p in UNP.rglob("*.xml"))
rels = sorted(str(p.relative_to(UNP)) for p in UNP.rglob("*.rels"))
print("media:", len(media))
print("embeddings:", len(emb))
print("xml:", len(xmls))
print("rels:", rels)
print("has document.xml:", (UNP / "word/document.xml").is_file())
info = {"media": media, "embeddings": emb, "relfiles": rels}
(BASE / "s1_unpack_meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
