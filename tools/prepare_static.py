"""Restore large static assets from their lossless, versioned archives."""

import gzip
import hashlib

from locations import ROOT

ASSETS = [
    {
        "name": "data.json",
        "sha256": "2e558da2b6d8832a2dd8a939182888b5fed94629e8e454ed9873e61552bcdba0",
    },
    {
        "name": "language-families.xml",
        "sha256": "4e75be48f4b197a83d9da0d7f7f921bd151d67783cecb4e640aec1f7a1d99416",
    },
]

for asset in ASSETS:
    data = gzip.decompress((ROOT / "source-data" / "packed" / (asset["name"] + ".gz")).read_bytes())
    if hashlib.sha256(data).hexdigest() != asset["sha256"]:
        raise ValueError("Checksum mismatch: " + asset["name"])
    (ROOT / "dist" / asset["name"]).write_bytes(data)
    print("Restored " + asset["name"])
