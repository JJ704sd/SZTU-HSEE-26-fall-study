"""Portable regressions for textual DOCX inspection; no course files needed."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "inspect_docx.py"
SPEC = importlib.util.spec_from_file_location("inspect_docx", SCRIPT)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
W_URI = PROBE.NS["w"]


def paragraph(content):
    return ET.fromstring(f'<w:p xmlns:w="{W_URI}">{content}</w:p>')


class InspectDocxTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sztu-report-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fixture = self.root / "sample.docx"
        self.write_fixture()

    def write_fixture(self, with_styles=False):
        content = (
            f'<w:document xmlns:w="{W_URI}"><w:body><w:p>'
            '<w:r><w:t>private-fixture-text</w:t><w:br/><w:tab/>'
            '<w:t>run()</w:t></w:r></w:p>'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:left="1800" w:right="1800" w:top="1440" w:bottom="1440"/>'
            '</w:sectPr></w:body></w:document>'
        )
        with ZipFile(self.fixture, "w") as package:
            package.writestr("word/document.xml", content)
            if with_styles:
                package.writestr("word/styles.xml", (
                    f'<w:styles xmlns:w="{W_URI}">'
                    '<w:style w:type="paragraph" w:default="1" w:styleId="body">'
                    '<w:name w:val="Normal"/><w:basedOn w:val="base"/></w:style>'
                    '<w:style w:type="paragraph" w:styleId="base">'
                    '<w:rPr><w:sz w:val="24"/></w:rPr></w:style></w:styles>'
                ))

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPT), str(self.fixture), *args],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )

    def test_code_linebreak_and_indentation(self):
        node = paragraph('<w:r><w:t>if ready:</w:t><w:br/><w:tab/><w:t>run()</w:t></w:r>')
        self.assertEqual(PROBE.paragraph_text(node), "if ready:\n\trun()")

    def test_multiple_runs_and_carriage_return(self):
        node = paragraph(
            '<w:r><w:t xml:space="preserve">  a = </w:t></w:r>'
            '<w:r><w:t>1</w:t><w:cr/><w:t>b = 2</w:t></w:r>'
        )
        self.assertEqual(PROBE.paragraph_text(node), "  a = 1\nb = 2")

    def test_nested_text_box_is_separate(self):
        node = paragraph(
            '<w:r><w:t>host</w:t><w:drawing><w:txbxContent><w:p>'
            '<w:r><w:t>textbox</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r>'
        )
        self.assertEqual(PROBE.paragraph_text(node), "host")
        self.assertEqual(PROBE.paragraph_text(node.find(".//w:p", PROBE.NS)), "textbox")

    def test_final_inline_revision_view(self):
        node = paragraph(
            '<w:del><w:r><w:delText>old</w:delText></w:r></w:del>'
            '<w:moveFrom><w:r><w:t>moved</w:t></w:r></w:moveFrom>'
            '<w:ins><w:r><w:t>new</w:t></w:r></w:ins>'
        )
        self.assertEqual(PROBE.paragraph_text(node), "new")

    def test_summary_dimensions_and_default_text_exclusion(self):
        result = PROBE.inspect(self.fixture)
        compact = PROBE.summary(result)
        self.assertEqual(compact["sections"][0]["margins_cm"]["left"], 3.175)
        self.assertEqual(compact["paragraph_count_with_text"], 1)
        self.assertEqual(result["styles"], {})
        self.assertNotIn("private-fixture-text", json.dumps(result))
        self.assertNotIn("paragraphs", compact)
        detailed = PROBE.inspect(self.fixture, include_text=True)
        self.assertEqual(detailed["paragraphs"][0]["text"], "private-fixture-text\n\trun()")

    def test_style_ancestry_and_read_only_input(self):
        self.write_fixture(with_styles=True)
        before = hashlib.sha256(self.fixture.read_bytes()).hexdigest()
        result = PROBE.inspect(self.fixture)
        self.assertEqual(set(result["styles"]), {"body", "base"})
        self.assertEqual(before, hashlib.sha256(self.fixture.read_bytes()).hexdigest())

    def test_cli_summary_and_clobber_refusal(self):
        output = self.root / "existing.json"
        output.write_text("keep me", encoding="utf-8")
        result = self.cli("--summary", "--output", str(output))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_text(encoding="utf-8"), "keep me")
        result = self.cli("--summary")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["mode"], "summary")
        self.assertEqual(self.cli("--summary", "--include-text").returncode, 2)

    def test_invalid_package_is_rejected_without_traceback(self):
        self.fixture.write_bytes(b"invalid package")
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
