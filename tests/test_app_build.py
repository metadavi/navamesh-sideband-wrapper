"""
test_app_build.py — static guards for FarmApp module scope bugs.

Regression: FarmApp.build() used os.environ near the top while ALSO doing a
local `import os` further down. The local import makes `os` function-local for
the whole function, so the earlier use raised UnboundLocalError — but only at
launch (build() needs a real Kivy Window, so the unit tests, which build
FarmApp via __new__, never executed it and never caught the crash on-device).

This guard parses app.py and asserts no function locally re-imports a name that
is already imported at module scope (the shadowing that caused the crash).
"""
from __future__ import annotations

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parents[1] / "sbapp" / "farmui" / "app.py"


def _module_level_import_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
    return names


def _local_import_names(func: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split(".")[0])
    return names


def test_no_function_shadows_a_module_level_import():
    tree = ast.parse(APP.read_text())
    module_imports = _module_level_import_names(tree)
    offenders = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            clash = module_imports & _local_import_names(node)
            if clash:
                offenders[node.name] = sorted(clash)
    assert not offenders, (
        f"function(s) locally re-import module-level name(s): {offenders}. "
        "A local `import X` shadows the module-level X for the whole function "
        "and causes UnboundLocalError if X is used before that local import "
        "(this crashed FarmApp.build() on-device)."
    )
