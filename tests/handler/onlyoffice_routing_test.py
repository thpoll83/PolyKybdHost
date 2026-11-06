"""The SHIPPED ONLYOFFICE Desktop Editors routing in `overlay-mapping.poly.yaml`.

One process (`DesktopEditors`) hosts the Document, Spreadsheet and Presentation
editors as tabs, so the entry routes on the file extension in the window title
(`titles-match`). What it pins:

* every process name the host can report resolves to the entry;
* a spreadsheet or presentation extension loads that editor's set, on Windows,
  Linux and macOS, including the "*" prefix of an unsaved change;
* a document extension, a PDF, an unsaved "Document1" style title and an empty
  title (the start page) load the Document set;
* an extension that does not end the file name ("Notes.xlsx-old") or a name
  that only mentions it ("xlsx tips.docx") does not change the set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"


def _set(editor, mac=False):
    stem = f"onlyoffice_{editor}_template" + ("_mac" if mac else "")
    files = [f"{stem}.mods.png", f"{stem}.combo.mods.png"]
    if mac:
        files.append(f"{stem}.extra.mods.png")
    return files


DOC, SHEET, PRES = _set("document"), _set("spreadsheet"), _set("presentation")
DOC_MAC, SHEET_MAC, PRES_MAC = (_set("document", True), _set("spreadsheet", True),
                                _set("presentation", True))
NAMES = ("desktopeditors", "onlyoffice", "onlyoffice-desktopeditors",
         "org.onlyoffice.desktopeditors")


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as telegram_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        # Skip only for a missing third-party backend or an Xlib display error.
        # A missing polyhost module is a real failure.
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


class OnlyofficeRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, title, os_name="windows", app="desktopeditors"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_every_process_name_resolves(self):
        for app in NAMES:
            self.assertEqual(self._route("Book1.xlsx", "linux", app), SHEET, app)

    def test_spreadsheet_extensions_load_the_spreadsheet_set(self):
        for title in ("Book1.xlsx", "*Budget.XLSX", "data.csv", "plan.ods",
                      "old.xls", "Book1.xlsx (Read only)"):
            for os_name in ("windows", "linux"):
                self.assertEqual(self._route(title, os_name), SHEET, (title, os_name))
            self.assertEqual(self._route(title, "macos"), SHEET_MAC, title)

    def test_presentation_extensions_load_the_presentation_set(self):
        # "Notes.xlsx final.pptx": only the final extension counts.
        for title in ("Presentation1.pptx", "*Talk.odp", "deck.ppt", "show.ppsx",
                      "Notes.xlsx final.pptx", "Notes.xlsx final.pptx (Read only)"):
            self.assertEqual(self._route(title), PRES, title)
            self.assertEqual(self._route(title, "macos"), PRES_MAC, title)

    def test_other_titles_load_the_document_set(self):
        for title in ("Document1.docx", "Report.odt", "scan.pdf", "Document1",
                      "", "ONLYOFFICE"):
            self.assertEqual(self._route(title), DOC, repr(title))
            self.assertEqual(self._route(title, "macos"), DOC_MAC, repr(title))

    def test_extension_must_end_the_file_name(self):
        self.assertEqual(self._route("Notes.xlsx-old"), DOC)
        self.assertEqual(self._route("xlsx tips.docx"), DOC)

    def test_every_named_file_exists(self):
        files = DOC + SHEET + PRES + DOC_MAC + SHEET_MAC + PRES_MAC
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
