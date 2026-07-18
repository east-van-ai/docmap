"""
Unit tests for the AST/docstring/YAML layer of docmap.cli:
first_doc_sentence, format_args, collect_defs, yaml_escape, dump_yaml.
"""

import ast

import pytest

from docmap.cli import (
    collect_defs,
    dump_yaml,
    first_doc_sentence,
    format_args,
    yaml_escape,
)


def _first_func_node(src: str):
    tree = ast.parse(src)
    return tree.body[0]


# ---------- first_doc_sentence ----------


def test_first_doc_sentence_simple():
    node = _first_func_node('def f():\n    """Do a thing."""\n    pass')
    assert first_doc_sentence(node) == "Do a thing."


def test_first_doc_sentence_multiline_paragraph():
    src = 'def f():\n    """Do a thing.\n\n    More detail here that should be dropped.\n    """\n    pass'
    node = _first_func_node(src)
    assert first_doc_sentence(node) == "Do a thing."


def test_first_doc_sentence_no_terminator():
    node = _first_func_node('def f():\n    """No terminator here"""\n    pass')
    assert first_doc_sentence(node) == "No terminator here"


def test_first_doc_sentence_missing():
    node = _first_func_node("def f():\n    pass")
    assert first_doc_sentence(node) == ""


def test_first_doc_sentence_question_mark():
    node = _first_func_node('def f():\n    """Is this it? Yes it is."""\n    pass')
    assert first_doc_sentence(node) == "Is this it?"


# ---------- format_args ----------


def test_format_args_all_kinds():
    src = "def f(a, b, /, c, *args, d, **kwargs): pass"
    node = _first_func_node(src)
    assert format_args(node.args) == "a, b, c, *args, d, **kwargs"


def test_format_args_empty():
    node = _first_func_node("def f(): pass")
    assert format_args(node.args) == ""


# ---------- yaml_escape ----------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", '""'),
        ("plain", "plain"),
        ("has: colon", '"has: colon"'),
        (" leading space", '" leading space"'),
        ('has "quote"', '"has \\"quote\\""'),
    ],
)
def test_yaml_escape(raw, expected):
    assert yaml_escape(raw) == expected


# ---------- collect_defs ----------


def test_collect_defs_skips_dunder_and_private_by_default():
    src = (
        "def public():\n    pass\n"
        "def _private():\n    pass\n"
        "def __dunder__():\n    pass\n"
    )
    tree = ast.parse(src)
    entries = collect_defs(tree, include_private=False)
    names = {e["name"] for e in entries}
    assert names == {"public"}


def test_collect_defs_include_private():
    src = "def _private():\n    pass\n"
    tree = ast.parse(src)
    entries = collect_defs(tree, include_private=True)
    assert {e["name"] for e in entries} == {"_private"}


def test_collect_defs_class_and_methods_qualified():
    src = (
        "class Foo:\n"
        "    def bar(self):\n"
        "        pass\n"
        "    class Inner:\n"
        "        def baz(self):\n"
        "            pass\n"
    )
    tree = ast.parse(src)
    entries = collect_defs(tree, include_private=False)
    names = {e["name"] for e in entries}
    assert names == {"Foo", "Foo.bar", "Foo.Inner", "Foo.Inner.baz"}


def test_collect_defs_does_not_descend_into_function_bodies():
    src = "def outer():\n    def inner():\n        pass\n    return inner\n"
    tree = ast.parse(src)
    entries = collect_defs(tree, include_private=False)
    assert {e["name"] for e in entries} == {"outer"}


# ---------- dump_yaml ----------


def test_dump_yaml_skips_empty_files():
    file_entries = {
        "empty.py": [],
        "has_stuff.py": [{"name": "f", "args": "", "doc": "d", "line": 1}],
    }
    out = dump_yaml(file_entries)
    assert "empty.py" not in out
    assert "has_stuff.py:" in out
    assert 'def: "f()"' in out or "def: f()" in out


def test_dump_yaml_class_marker():
    file_entries = {
        "a.py": [{"name": "Foo", "args": "", "doc": "", "line": 3, "is_class": True}]
    }
    out = dump_yaml(file_entries)
    assert "class: Foo" in out
