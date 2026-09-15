from perturb.graph_export import render_dot, render_mermaid, subtree


def _subtree_fixture():
    def _i(number, title, epic, state="OPEN"):
        return {
            str(number): {
                "number": number,
                "title": title,
                "epic": epic,
                "state": state,
                "blocks": [],
            }
        }

    issues = {}
    issues.update(_i(1, "Epic: Graph and ready queue", None))
    issues.update(_i(5, "next and ready verbs", 1))
    issues.update(_i(8, "sub-epic", 1))
    issues.update(_i(10, "grandchild", 8))
    issues.update(_i(99, "unrelated", None))
    return issues


def _render_fixture():
    return {
        "1": {
            "number": 1,
            "title": "Epic: Graph and ready queue",
            "epic": None,
            "state": "OPEN",
            "blocks": [],
        },
        "4": {"number": 4, "title": "graph derivation", "epic": 1, "state": "CLOSED", "blocks": []},
        "5": {
            "number": 5,
            "title": "next and ready verbs",
            "epic": 1,
            "state": "OPEN",
            "blocks": [6],
        },
        "6": {"number": 6, "title": "show verb", "epic": 1, "state": "OPEN", "blocks": []},
    }


_MERMAID_FULL = (
    "graph TD\n"
    '  N1["#1 Epic: Graph and ready queue"]\n'
    '  N4["#4 graph derivation"]\n'
    '  N5["#5 next and ready verbs"]\n'
    '  N6["#6 show verb"]\n'
    "  N1 --> N4\n"
    "  N1 --> N5\n"
    "  N1 --> N6\n"
    "  N5 -->|blocks| N6\n"
    "  classDef closed fill:#eee,stroke:#999,color:#999;\n"
    "  class N4 closed;\n"
)


def test_render_mermaid_matches_documented_layout():
    assert render_mermaid(_render_fixture()) == _MERMAID_FULL


def _dot_render_fixture():
    return {
        "1": {
            "number": 1,
            "title": "Epic: Graph and ready queue",
            "epic": None,
            "state": "OPEN",
            "blocks": [],
        },
        "4": {
            "number": 4,
            "title": 'graph "derivation"',
            "epic": 1,
            "state": "CLOSED",
            "blocks": [],
        },
        "5": {
            "number": 5,
            "title": "next and ready verbs",
            "epic": 1,
            "state": "OPEN",
            "blocks": [6],
        },
        "6": {"number": 6, "title": "show verb", "epic": 1, "state": "OPEN", "blocks": []},
    }


_DOT_FULL = (
    "digraph perturb {\n"
    '  N1 [label="#1 Epic: Graph and ready queue"];\n'
    '  N4 [label="#4 graph \\"derivation\\"", style=dashed, color="#999999",'
    ' fontcolor="#999999"];\n'
    '  N5 [label="#5 next and ready verbs"];\n'
    '  N6 [label="#6 show verb"];\n'
    "  N1 -> N4;\n"
    "  N1 -> N5;\n"
    "  N1 -> N6;\n"
    '  N5 -> N6 [label="blocks"];\n'
    "}\n"
)


_DOT_EPIC8 = (
    "digraph perturb {\n"
    '  N8 [label="#8 sub-epic"];\n'
    '  N10 [label="#10 grandchild"];\n'
    "  N8 -> N10;\n"
    "}\n"
)


def test_render_dot_epic_restricts_to_subtree():
    assert render_dot(_subtree_fixture(), epic=8) == _DOT_EPIC8


def test_render_dot_matches_documented_layout():
    assert render_dot(_dot_render_fixture()) == _DOT_FULL


def test_render_mermaid_escapes_quotes_in_labels():
    issues = {
        "7": {
            "number": 7,
            "title": 'has "quotes" and [brackets]',
            "epic": None,
            "state": "OPEN",
            "blocks": [],
        }
    }
    result = render_mermaid(issues)
    assert '  N7["#7 has &quot;quotes&quot; and [brackets]"]' in result


_MERMAID_EPIC8 = 'graph TD\n  N8["#8 sub-epic"]\n  N10["#10 grandchild"]\n  N8 --> N10\n'


def test_render_mermaid_epic_restricts_to_subtree():
    assert render_mermaid(_subtree_fixture(), epic=8) == _MERMAID_EPIC8


def test_subtree_collects_transitive_descendants():
    issues = _subtree_fixture()
    assert subtree(issues, 1) == {1, 5, 8, 10}
