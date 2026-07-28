"""Game-independent selection and tuning helpers for the Anime TV mod."""


def has_affordance(value, affordance_id):
    affordances = getattr(value, "_super_affordances", ()) or ()
    return any(
        getattr(affordance, "guid64", None) == affordance_id
        for affordance in affordances
    )


def inject_into_televisions(object_tunings, custom_affordance, marker_affordance_id):
    """Append the custom affordance to TV tunings and return the changed count."""
    changed = 0
    custom_id = getattr(custom_affordance, "guid64", None)
    for object_tuning in object_tunings:
        if not has_affordance(object_tuning, marker_affordance_id):
            continue
        if custom_id is not None and has_affordance(object_tuning, custom_id):
            continue
        affordances = tuple(getattr(object_tuning, "_super_affordances", ()) or ())
        object_tuning._super_affordances = affordances + (custom_affordance,)
        changed += 1
    return changed


def _distance_squared(first, second):
    first_position = getattr(first, "position", None)
    second_position = getattr(second, "position", None)
    if first_position is None or second_position is None:
        return float("inf")
    delta_x = first_position.x - second_position.x
    delta_z = first_position.z - second_position.z
    return delta_x * delta_x + delta_z * delta_z


def select_nearest_television(objects, sim, marker_affordance_id):
    """Return the nearest loaded object that exposes the marker TV affordance."""
    televisions = (
        obj for obj in objects if has_affordance(obj, marker_affordance_id)
    )
    return min(televisions, key=lambda obj: _distance_squared(obj, sim), default=None)
