from src.anime_tv.core import inject_into_televisions, select_nearest_television


class Position:
    def __init__(self, x, z):
        self.x = x
        self.z = z


class Affordance:
    def __init__(self, guid64):
        self.guid64 = guid64


class Tuning:
    def __init__(self, affordances):
        self._super_affordances = tuple(affordances)


class GameObject(Tuning):
    def __init__(self, x, z, affordances):
        super().__init__(affordances)
        self.position = Position(x, z)


class Sim:
    def __init__(self, x, z):
        self.position = Position(x, z)


def test_inject_into_televisions_only_targets_marker_affordance():
    marker = Affordance(9110)
    custom = Affordance(123456)
    television = Tuning((marker,))
    other_object = Tuning(())

    count = inject_into_televisions((television, other_object), custom, marker.guid64)

    assert count == 1
    assert television._super_affordances == (marker, custom)
    assert other_object._super_affordances == ()


def test_inject_into_televisions_does_not_add_duplicates():
    marker = Affordance(9110)
    custom = Affordance(123456)
    television = Tuning((marker, custom))

    count = inject_into_televisions((television,), custom, marker.guid64)

    assert count == 0
    assert television._super_affordances == (marker, custom)


def test_select_nearest_television_filters_non_televisions():
    marker = Affordance(9110)
    far_tv = GameObject(8, 0, (marker,))
    near_tv = GameObject(2, 1, (marker,))
    nearest_non_tv = GameObject(0, 0, ())

    result = select_nearest_television(
        (far_tv, nearest_non_tv, near_tv), Sim(0, 0), marker.guid64
    )

    assert result is near_tv


def test_select_nearest_television_returns_none_when_unavailable():
    assert select_nearest_television((GameObject(1, 1, ()),), Sim(0, 0), 9110) is None
