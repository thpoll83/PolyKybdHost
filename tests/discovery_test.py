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

    def test_no_test_class_is_defined_AFTER_a_main_guard(self):
        """\u26a0\ufe0f A class below `if __name__ == "__main__":` never runs when the
        file is run DIRECTLY, and the run still prints OK.

        `unittest.main()` executes at the guard, before the rest of the module
        is defined, so every class below it is simply absent -- and the lower
        count is the only trace. Sibling of the duplicate-method check above:
        both are ways a test stops existing while the board stays green, and
        both need the AST because by the time anything is imported the evidence
        is gone.

        CI is unaffected (it runs the suite through `scripts/run_tests.py`,
        where `__name__` is never `__main__`), which is exactly why this went
        unnoticed: the cost falls on a contributor running one file by hand,
        who is also the person least likely to question an OK.

        Measured on `active_window_test.py`, which had FOUR guards and 11 of
        its 22 classes below the first: `python tests/handler/active_window_test.py`
        reported `Ran 61 tests, OK` against `Ran 104 tests, OK` under
        `-m unittest` (#397). The sweep that followed found 11 more files and
        27 more stranded classes (#398).

        The guard is identified as a module-level `If` whose test mentions
        `__main__`, so the string in a docstring or a fixture is never
        mistaken for one.
        """
        root = pathlib.Path(__file__).resolve().parent
        files = sorted(root.rglob("*_test.py"))
        self.assertGreater(len(files), 100, "the sweep found almost nothing")
        stranded = []
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            guards = [n for n in tree.body
                      if isinstance(n, ast.If) and "__main__" in ast.dump(n.test)]
            if not guards:
                continue
            first = guards[0].lineno
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.lineno > first:
                    stranded.append(
                        f"{path.relative_to(root)}::{node.name} is defined after"
                        f" the __main__ guard on line {first}, so a direct run"
                        f" never reaches it")
        self.assertEqual(stranded, [], "\n".join(stranded))

if __name__ == "__main__":
    unittest.main()
