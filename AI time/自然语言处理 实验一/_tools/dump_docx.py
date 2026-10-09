"""Dump DOCX text (incl. tables) with UTF-8 stdout for reading on Windows."""
import sys
import zipfile
import re
from pathlib import Path
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def para_text(p):
    parts = []
    for node in p.iter():
        tag = node.tag.split("}")[-1]
        if tag == "t":
            parts.append(node.text or "")
        elif tag == "tab":
            parts.append("\t")
        elif tag in ("br", "cr"):
            parts.append("\n")
    return "".join(parts)


def dump(path):
    print("=" * 78)
    print("FILE:", path)
    print("=" * 78)
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find("w:body", NS)
    for child in body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            style = ""
            pPr = child.find("w:pPr", NS)
            if pPr is not None:
                ps = pPr.find("w:pStyle", NS)
                if ps is not None:
                    style = ps.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") or ""
            txt = para_text(child)
            prefix = f"[{style}] " if style else ""
            if txt.strip() or style:
                print(prefix + txt)
        elif tag == "tbl":
            print("--- TABLE ---")
            for tr in child.findall("w:tr", NS):
                cells = []
                for tc in tr.findall("w:tc", NS):
                    cells.append(
                        " ".join(para_text(p) for p in tc.findall("w:p", NS)).strip()
                    )
                print(" | ".join(cells))
            print("--- END TABLE ---")


for arg in sys.argv[1:]:
    dump(Path(arg))
