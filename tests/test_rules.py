import pytest
from hypothesis import given
from hypothesis import strategies as st

from testbudget.rules import (
    RuleContext,
    changed_tests_next,
    file_of_test,
    pin_first,
    pinned_tests,
)


def make_test(name, score=1.0, duration=1.0):
    return {
        "test_name": name,
        "score": score,
        "duration": duration,
        "failure_count": 0,
        "linked_to_change": False,
        "reason": "historical runtime",
    }


def names(tests):
    return [test["test_name"] for test in tests]


RANKED = [
    make_test("tests/test_a.py::test_one", score=3.0),
    make_test("tests/test_b.py::test_two", score=2.0),
    make_test("tests/test_c.py::test_three", score=1.0),
]

test_ids = st.lists(
    st.text(alphabet="abcdefgh_", min_size=1, max_size=6).map(
        lambda name: f"tests/test_{name}.py::test_{name}"
    ),
    unique=True,
    min_size=1,
    max_size=12,
)


def test_pinned_test_moves_to_the_front():
    context = RuleContext(config={"pins": ["tests/test_c.py::test_three"]})
    result = pin_first(RANKED, context)
    assert names(result) == [
        "tests/test_c.py::test_three",
        "tests/test_a.py::test_one",
        "tests/test_b.py::test_two",
    ]
    assert result[0]["rule"] == "pinned"
    assert "rule" not in result[1]


def test_pins_as_mapping_of_test_to_files_are_read():
    config = {"pins": {"tests/test_b.py::test_two": ["src/pay.py"]}}
    assert pinned_tests(config) == {"tests/test_b.py::test_two"}


def test_several_pinned_tests_keep_their_ranked_order():
    pins = ["tests/test_c.py::test_three", "tests/test_b.py::test_two"]
    result = pin_first(RANKED, RuleContext(config={"pins": pins}))
    assert names(result)[:2] == pins[::-1]


def test_pin_for_an_unknown_test_is_ignored():
    context = RuleContext(config={"pins": ["tests/test_x.py::test_gone"]})
    assert names(pin_first(RANKED, context)) == names(RANKED)


def test_no_pins_leaves_the_order_unchanged():
    assert names(pin_first(RANKED, RuleContext())) == names(RANKED)


def test_pin_first_does_not_mutate_its_input():
    ranked = [dict(test) for test in RANKED]
    pin_first(ranked, RuleContext(config={"pins": ["tests/test_c.py::test_three"]}))
    assert ranked == RANKED


@pytest.mark.parametrize("pins", ["tests/test_a.py::test_one", 3, [""], [None]])
def test_malformed_pins_are_rejected(pins):
    with pytest.raises(ValueError, match="pin"):
        pin_first(RANKED, RuleContext(config={"pins": pins}))


@given(ids=test_ids, data=st.data())
def test_pinned_test_is_always_first(ids, data):
    pins = data.draw(st.lists(st.sampled_from(ids), min_size=1, unique=True))
    ranked = [make_test(test_id) for test_id in ids]
    result = pin_first(ranked, RuleContext(config={"pins": pins}))
    assert result[0]["test_name"] in pins
    assert set(names(result[: len(pins)])) == set(pins)


@pytest.mark.parametrize(
    ("test_id", "expected"),
    [
        ("tests/test_a.py::test_one", "tests/test_a.py"),
        ("tests/test_a.py::TestCase::test_one", "tests/test_a.py"),
        ("e2e/cart.spec.ts › adds an item", "e2e/cart.spec.ts"),
        (r"tests\test_a.py::test_one", "tests/test_a.py"),
        ("tests/test_a.py", "tests/test_a.py"),
    ],
)
def test_file_of_test_is_the_part_before_the_separator(test_id, expected):
    assert file_of_test(test_id) == expected


def test_test_whose_file_changed_moves_to_the_front():
    context = RuleContext(changed_files=["./tests/test_b.py", "src/pay.py"])
    result = changed_tests_next(RANKED, context)
    assert names(result)[0] == "tests/test_b.py::test_two"
    assert result[0]["rule"] == "changed test file"
    assert names(result)[1:] == [
        "tests/test_a.py::test_one",
        "tests/test_c.py::test_three",
    ]


def test_playwright_spec_change_moves_its_tests():
    ranked = [
        make_test("e2e/home.spec.ts › loads"),
        make_test("e2e/cart.spec.ts › adds"),
    ]
    context = RuleContext(changed_files=["e2e/cart.spec.ts"])
    assert names(changed_tests_next(ranked, context))[0] == "e2e/cart.spec.ts › adds"


def test_source_only_change_leaves_the_order_unchanged():
    context = RuleContext(changed_files=["src/pay.py"])
    assert names(changed_tests_next(RANKED, context)) == names(RANKED)


def test_changed_files_given_as_a_string_is_rejected():
    with pytest.raises(TypeError, match="list of paths"):
        changed_tests_next(RANKED, RuleContext(changed_files="tests/test_b.py"))
