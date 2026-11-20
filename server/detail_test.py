import json

import rpa1688

d = rpa1688.collect_detail("http://detail.1688.com/offer/991730585225.html")
print(json.dumps({k: v for k, v in d.items() if k != "images"}, ensure_ascii=False, indent=2))
print("images:", len(d.get("images", [])))
