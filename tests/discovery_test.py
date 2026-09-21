import ast
import collections
import pathlib
import unittest

class TestDiscovery(unittest.TestCase):
    def test_discovery_works(self):
        self.assertTrue(True)

    def test_no_test_class_defines_a_method_name_TWICE(self):
        """\u26a0\ufe0f A duplicate method DELETES the earlier test, and every other
        check here reads as fine.

        Python keeps the last definition, so the shadowed one never runs, never
        fails, and never appears in the `Ran N` line -- which is the one signal
        this repo relies on to notice a test that stopped existing. It cannot
        help here: the count simply never counted the lost test. The shadowed
        body may not even be valid any more (the instance that prompted this
        referenced two imports the file no longer had), and nothing would say so.

        It is a scripted-edit hazard above all: replacing a slice that starts
        at the wrong anchor leaves the original definition in place, and the
        suite goes green. That is the same class as the CLAUDE.md rule about
        `s.replace(anchor, new)` dropping whatever sits between two anchors.
        Found by CodeQL on `active_window_test.py`, which is a reviewer that
        only reads a pull request's diff -- this reads the whole tree.

        AST, not introspection: by the time the module is imported the earlier
        definition is already gone.
        """
        root = pathlib.Path(__file__).resolve().parent
        files = sorted(root.rglob("*_test.py"))
        self.assertGreater(len(files), 100, "the sweep found almost nothing")
        dupes = []
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                names = [b.name for b in node.body
                         if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))]
                for name, count in collections.Counter(names).items():
                    if count > 1:
                        dupes.append(
                            f"{path.relative_to(root)}::{node.name}::{name}"
                            f" defined {count} times")
        self.assertEqual(dupes, [], "\n".join(dupes))

if __name__ == "__main__":
    unittest.main()
