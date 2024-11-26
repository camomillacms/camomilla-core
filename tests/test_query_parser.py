import pytest
from django.db.models import Q
from camomilla.utils.query_parser import (
    ConditionParser,
)


@pytest.mark.parametrize(
    "query, expected_q",
    [
        # Single condition
        ("name__icontains=foo", Q(name__icontains="foo")),
        # Multiple conditions with AND
        (
            "name__icontains=foo AND age__gt=21",
            Q(name__icontains="foo") & Q(age__gt=21),
        ),
        # Multiple conditions with OR
        (
            "name__icontains=foo OR name__icontains=bar",
            Q(name__icontains="foo") | Q(name__icontains="bar"),
        ),
        # Mixed AND and OR conditions
        (
            "name__icontains=foo OR (age__gt=21 AND city__iexact='New York')",
            Q(name__icontains="foo") | (Q(age__gt=21) & Q(city__iexact="New York")),
        ),
        # Nested parentheses with OR inside AND
        (
            "((name__icontains=foo) OR (name__icontains=bar)) AND name__icontains=baz",
            (Q(name__icontains="foo") | Q(name__icontains="bar"))
            & Q(name__icontains="baz"),
        ),
        # Complex nested conditions with multiple OR and AND
        (
            "((name__icontains=foo) OR (name__icontains=bar) OR (name__icontains=buz)) AND age__gt=25 AND city__iexact='LA'",
            (
                Q(name__icontains="foo")
                | Q(name__icontains="bar")
                | Q(name__icontains="buz")
            )
            & Q(age__gt=25)
            & Q(city__iexact="LA"),
        ),
        # Single condition with no parentheses
        ("age__lte=30", Q(age__lte=30)),
        # Simple nested OR and AND with more levels of nesting
        (
            "(name__icontains=foo AND (age__gt=21 OR city__iexact='New York')) OR country__iexact='US'",
            (Q(name__icontains="foo") & (Q(age__gt=21) | Q(city__iexact="New York")))
            | Q(country__iexact="US"),
        ),
    ],
)
def test_condition_parser(query, expected_q):
    parser = ConditionParser(query)
    q_object = parser.parse_to_q()
    assert q_object.__str__() == expected_q.__str__()
