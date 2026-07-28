"""In-game registration and command for the Xem Anime TV interaction."""

import services
import sims4.commands
import sims4.log
from interactions.context import InteractionContext, QueueInsertStrategy
from interactions.priority import Priority
from sims4.resources import Types
from sims4.tuning.instance_manager import InstanceManager

from anime_tv.constants import ANIME_INTERACTION_ID, BASE_WATCH_INTERACTION_ID
from anime_tv.core import inject_into_televisions, select_nearest_television
from helpers.injector import inject


logger = sims4.log.Logger("tomis_AnimeTV", default_owner="tomis")


def _get_anime_affordance():
    return services.get_instance_manager(Types.INTERACTION).get(
        ANIME_INTERACTION_ID, pack_safe=True
    )


@inject(InstanceManager, "load_data_into_class_instances")
def _inject_anime_interaction(original, self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    if self.TYPE != Types.OBJECT:
        return result

    try:
        affordance = _get_anime_affordance()
        if affordance is not None:
            inject_into_televisions(
                self._tuned_classes.values(), affordance, BASE_WATCH_INTERACTION_ID
            )
    except Exception:
        logger.exception("Failed to add Xem Anime to television tunings")
    return result


def _get_active_sim(connection):
    client_manager = services.client_manager()
    client = client_manager.get(connection) if connection is not None else None
    if client is None:
        client = client_manager.get_first_client()
    if client is not None and client.active_sim is not None:
        return client.active_sim
    return services.get_active_sim()


@sims4.commands.Command("anime.watch", command_type=sims4.commands.CommandType.Live)
def anime_watch(_connection=None):
    output = sims4.commands.CheatOutput(_connection)
    sim = _get_active_sim(_connection)
    if sim is None:
        output("Xem Anime: không tìm thấy Sim đang điều khiển.")
        return False

    affordance = _get_anime_affordance()
    if affordance is None:
        output("Xem Anime: thiếu file tomis_AnimeTV.package.")
        return False

    television = select_nearest_television(
        services.object_manager().values(), sim, BASE_WATCH_INTERACTION_ID
    )
    if television is None:
        output("Xem Anime: không tìm thấy TV trên lô đất.")
        return False

    context = InteractionContext(
        sim,
        InteractionContext.SOURCE_SCRIPT_WITH_USER_INTENT,
        Priority.High,
        insert_strategy=QueueInsertStrategy.NEXT,
    )
    result = sim.push_super_affordance(affordance, television, context)
    if not result:
        output("Xem Anime: TV hiện không thể sử dụng.")
        return False

    output("Xem Anime: đã thêm vào hàng đợi của Sim.")
    return True
