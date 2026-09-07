from iip.validation_engine.returns import (
    ReturnPoint,
    cumulative_return,
    max_drawdown,
    simple_return,
)


def test_simple_return_is_deterministically_normalized():
    assert simple_return(100, 110) == 0.10


def test_cumulative_return_uses_same_normalization():
    assert (
        cumulative_return(
            (
                ReturnPoint("1", 100),
                ReturnPoint("2", 110),
            )
        )
        == 0.10
    )


def test_drawdown_is_deterministically_normalized():
    assert (
        max_drawdown(
            (
                ReturnPoint("1", 100),
                ReturnPoint("2", 120),
                ReturnPoint("3", 90),
            )
        )
        == 0.25
    )
