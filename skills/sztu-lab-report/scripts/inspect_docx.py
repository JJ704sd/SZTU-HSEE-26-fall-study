#!/usr/bin/env python3
"""Read explicit DOCX formatting without Word or third-party dependencies.

Style inheritance and theme data are reported for inspection, not resolved into
effective formatting. No visual or experimental correctness verdict is made.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
W = "{" + NS["w"] + "}"


def local(name):
    return name.rsplit("}", 1)[-1]


def node_data(node):
    if node is None:
        return None
    result = {"tag": local(node.tag)}
    if node.attrib:
        result["attrs"] = {local(k): v for k, v in node.attrib.items()}
    if list(node):
        result["children"] = [node_data(child) for child in node]
    return result


def value(node, path, default=None):
    child = node.find(path, NS)
    return child.get(W + "val", default) if child is not None else default


def inline_nodes(paragraph):
    """Keep this paragraph's content separate from nested text-box paragraphs."""
    def walk(node):
        for child in node:
            if child.tag in (W + "p", W + "del", W + "moveFrom"):
                continue
            yield child
            yield from walk(child)
    return walk(paragraph)


def paragraph_text(paragraph):
    controls = {W + "tab": "\t", W + "ptab": "\t", W + "br": "\n",
                W + "cr": "\n", W + "noBreakHyphen": "\u2011",
                W + "softHyphen": "\u00ad"}
    return "".join((node.text or "") if node.tag == W + "t" else controls.get(node.tag, "")
                   for node in inline_nodes(paragraph))


def inspect(path, include_text=False):
    with ZipFile(path) as package:
        document = ET.fromstring(package.read("word/document.xml"))
        styles = (ET.fromstring(package.read("word/styles.xml"))
                  if "word/styles.xml" in package.namelist() else None)
        style_map = ({s.get(W + "styleId"): s
                      for s in styles.findall("w:style", NS)} if styles is not None else {})
        defaults = ([sid for sid, s in style_map.items()
                     if s.get(W + "type") == "paragraph"
                     and s.get(W + "default") in ("1", "true", "on")])
        default_id = defaults[0] if defaults else None
        used = {default_id} if default_id else set()
        paragraphs = []
        profiles = Counter()
        run_formats = Counter()
        for index, paragraph in enumerate(document.findall(".//w:p", NS)):
            text = paragraph_text(paragraph)
            if not text.strip():
                continue
            style_id = value(paragraph, "w:pPr/w:pStyle", default_id)
            if style_id:
                used.add(style_id)
            run_profiles = Counter()
            for run in (node for node in inline_nodes(paragraph) if node.tag == W + "r"):
                character_style = value(run, "w:rPr/w:rStyle")
                if character_style:
                    used.add(character_style)
                raw = node_data(run.find("w:rPr", NS))
                run_profiles[json.dumps(raw, sort_keys=True, ensure_ascii=False)] += 1
            run_formats.update(run_profiles)
            pp = node_data(paragraph.find("w:pPr", NS))
            item = {"index": index, "text_length": len(text), "style_id": style_id,
                    "paragraph_properties": pp,
                    "run_property_groups": [{"properties": json.loads(k), "runs": v}
                                            for k, v in run_profiles.items()]}
            if include_text:
                item["text"] = text
            paragraphs.append(item)
            profiles[json.dumps({"style_id": style_id, "properties": pp},
                                sort_keys=True, ensure_ascii=False)] += 1

        tables = []
        for table in document.findall(".//w:tbl", NS):
            sid = value(table, "w:tblPr/w:tblStyle")
            if sid:
                used.add(sid)
            tables.append({
                "rows": len(table.findall("w:tr", NS)),
                "grid_twips": [int(c.get(W + "w", "0"))
                               for c in table.findall("w:tblGrid/w:gridCol", NS)],
                "properties": node_data(table.find("w:tblPr", NS)),
                "row_properties": [node_data(r.find("w:trPr", NS))
                                   for r in table.findall("w:tr", NS)],
                "cell_properties": [node_data(c.find("w:tcPr", NS))
                                    for c in table.findall("w:tr/w:tc", NS)],
            })

        # Include ancestors, linked character styles, and default table styles.
        used.update(sid for sid, s in style_map.items()
                    if s.get(W + "type") == "table" and s.get(W + "default") == "1")
        pending = list(used)
        while pending:
            sid = pending.pop()
            style = style_map.get(sid)
            if style is None:
                continue
            for relation in ("w:basedOn", "w:link"):
                linked = value(style, relation)
                if linked and linked not in used:
                    used.add(linked)
                    pending.append(linked)

        sections = []
        for section in document.findall(".//w:sectPr", NS):
            size = section.find("w:pgSz", NS)
            margin = section.find("w:pgMar", NS)
            info = {"raw": node_data(section)}
            if size is not None:
                info["page_cm"] = {k: round(int(size.get(W + k)) / 1440 * 2.54, 4)
                                   for k in ("w", "h") if size.get(W + k) is not None}
            if margin is not None:
                info["margins_cm"] = {
                    k: round(int(margin.get(W + k)) / 1440 * 2.54, 4)
                    for k in ("top", "bottom", "left", "right", "header", "footer", "gutter")
                    if margin.get(W + k) is not None}
            sections.append(info)

        themes = {}
        for name in package.namelist():
            if name.startswith("word/theme/") and name.endswith(".xml"):
                theme = ET.fromstring(package.read(name))
                themes[name] = node_data(theme.find(".//a:fontScheme", NS))
        fields = document.findall(".//w:instrText", NS)
        return {
            "source": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "format_scope": "explicit properties and related styles; no effective-style or visual verdict",
            "text_included": include_text,
            "sections": sections,
            "document_defaults": node_data(styles.find("w:docDefaults", NS)) if styles is not None else None,
            "styles": {sid: node_data(style_map[sid]) for sid in sorted(used) if sid in style_map},
            "theme_fonts": themes,
            "paragraph_count_with_text": len(paragraphs),
            "paragraph_property_groups": [{"profile": json.loads(k), "paragraphs": v}
                                          for k, v in profiles.most_common()],
            "run_property_groups": [{"properties": json.loads(k), "runs": v}
                                    for k, v in run_formats.most_common()],
            "paragraphs": paragraphs,
            "tables": tables,
            "drawing_extents_cm": [{"width": round(int(e.get("cx", "0")) / 360000, 4),
                                    "height": round(int(e.get("cy", "0")) / 360000, 4)}
                                   for e in document.findall(".//wp:extent", NS)],
            "media_files": [n for n in package.namelist()
                            if n.startswith("word/media/") and not n.endswith("/")],
            "field_instruction_fragments": len(fields),
            "notes": ["Field instructions do not by themselves indicate a broken field.",
                      "No PDF page count is inferred from DOCX cached metadata.",
                      "Text covers body paragraphs including text-box paragraphs; run breaks and tabs are preserved.",
                      "Deleted and moved-from inline text is excluded; this is not a full tracked-changes review.",
                      "Headers, footers, VML geometry, conditional table styling and rendered pagination need separate review."],
        }


def summary(result):
    """A bounded first look; keep full explicit-property output available."""
    sections = [{k: v for k, v in section.items() if k != "raw"}
                for section in result["sections"]]
    styles = {}
    for sid, style in result["styles"].items():
        styles[sid] = {child["tag"]: child for child in style.get("children", [])
                       if child["tag"] in ("name", "basedOn", "link", "pPr", "rPr")}
    return {
        "source": result["source"],
        "sha256": result["sha256"],
        "mode": "summary",
        "format_scope": result["format_scope"],
        "text_included": False,
        "sections": sections,
        "document_defaults": result["document_defaults"],
        "related_styles": styles,
        "paragraph_count_with_text": result["paragraph_count_with_text"],
        "common_paragraph_property_groups": result["paragraph_property_groups"][:8],
        "common_run_property_groups": result["run_property_groups"][:8],
        "tables": [{"index": i, "rows": table["rows"],
                    "grid_twips": table["grid_twips"],
                    "grid_width_cm": round(sum(table["grid_twips"]) / 1440 * 2.54, 4),
                    "properties": table["properties"]}
                   for i, table in enumerate(result["tables"])],
        "drawing_extents_cm": result["drawing_extents_cm"],
        "media_file_count": len(result["media_files"]),
        "field_instruction_fragments": result["field_instruction_fragments"],
        "notes": result["notes"] + ["Summary omits theme fonts and per-paragraph/cell details; inspect full output when needed."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--include-text", action="store_true", help="Include local paragraph text, line breaks and tabs")
    modes.add_argument("--summary", action="store_true", help="Compact formatting overview without paragraph text")
    parser.add_argument("--output", type=Path, help="Write a NEW JSON file; existing files are never overwritten")
    args = parser.parse_args()
    try:
        if args.docx.suffix.lower() != ".docx":
            raise ValueError("Expected a .docx file")
        result = inspect(args.docx, args.include_text)
        if args.summary:
            result = summary(result)
        data = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                output.write(data + "\n")
        else:
            print(data)
    except (OSError, ValueError, KeyError, BadZipFile, ET.ParseError) as error:
        print(f"inspect_docx: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
