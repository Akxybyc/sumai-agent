"""下载并解包店小宝 CRX 插件，供 Chrome「加载已解压的扩展程序」使用。"""
import io
import struct
import urllib.request
import zipfile
from pathlib import Path

URL = ("https://hj-data.oss-cn-shanghai.aliyuncs.com/ext/download-dxb/"
       "%E5%BA%97%E5%B0%8F%E5%AE%9D%E6%8F%92%E4%BB%B6.crx?t=1792984709099")
OUT = Path("D:/WorkBuddy/sumai_agent/dxb_ext")

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=60).read()
print("crx bytes:", len(raw))

if raw[:4] == b"Cr24":
    version = struct.unpack("<I", raw[4:8])[0]
    if version == 3:
        header_len = struct.unpack("<I", raw[8:12])[0]
        zip_start = 12 + header_len
    else:
        pubkey_len, sig_len = struct.unpack("<II", raw[8:16])
        zip_start = 16 + pubkey_len + sig_len
    blob = raw[zip_start:]
else:
    blob = raw

zf = zipfile.ZipFile(io.BytesIO(blob))
OUT.mkdir(parents=True, exist_ok=True)
zf.extractall(OUT)
print("extracted to", OUT)
print("manifest:", (OUT / "manifest.json").exists())
