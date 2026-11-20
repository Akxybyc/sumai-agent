import json
import re
from pathlib import Path

body = json.loads(Path("D:/WorkBuddy/sumai_agent/data/detail_debug.json").read_text(encoding="utf-8"))["body"]
print("len", len(body))
m = re.search(
    r"长\(cm\)\s*宽\(cm\)\s*高\(cm\)\s*体积\(cm.\s*重量\(g\)\s*"
    r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", body)
print("weight match:", bool(m), m.groups() if m else None)

idx = body.find("商品件重尺")
print("snippet:", body[idx:idx+120] if idx >= 0 else "not found")

keys = ["内胆材质", "品牌", "容量", "颜色"]
for k in keys:
    mm = re.search(rf"{k}\s+([^\s]{{1,28}})", body)
    print(k, "->", mm.group(1) if mm else None)
