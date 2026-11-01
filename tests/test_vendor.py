"""同梱の alphaTab と、その記録（VENDOR.md）・版の文字列（render.ALPHATAB_VERSION）が食い違わない。"""

import hashlib
import re
from pathlib import Path

import youtab
from youtab import render

VENDOR = Path(youtab.__file__).parent / "templates" / "vendor"


def _vendor_md() -> str:
    return (VENDOR / "VENDOR.md").read_text(encoding="utf-8")


def _section(md: str, title: str) -> str:
    return md.split(f"## {title}\n")[1].split("\n## ")[0]


def test_bundled_alphatab_matches_vendor_record():
    data = (VENDOR / "alphatab.min.js").read_bytes()
    section = _section(_vendor_md(), "alphatab.min.js")
    sha = re.search(r"\*\*SHA-256\*\*: `([0-9a-f]{64})`", section)
    size = re.search(r"\*\*Size\*\*: ([\d,]+) bytes", section)
    assert sha and size
    assert hashlib.sha256(data).hexdigest() == sha.group(1)
    assert len(data) == int(size.group(1).replace(",", ""))


def test_alphatab_version_is_the_same_everywhere():
    version = render.ALPHATAB_VERSION
    section = _section(_vendor_md(), "alphatab.min.js")
    assert f"**Version vendored**: `{version}`" in section
    assert f"@coderline/alphatab@{version}/dist/alphaTab.min.js" in section
    assert f"/blob/v{version}/LICENSE" in section
    head = (VENDOR / "alphatab.min.js").read_bytes()[:200].decode("utf-8")
    assert f"alphaTab v{version} " in head
    assert f"@coderline/alphatab@{version}/" in render.SOUNDFONT_URL
