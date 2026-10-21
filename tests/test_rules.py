import pytest
from hypothesis import given
from hypothesis import strategies as st

from testbudget.rules import RuleContext, pin_first, pinned_tests


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
