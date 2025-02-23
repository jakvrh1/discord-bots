# The discord bot doesn't like to execute things off the main thread. Instead, we
# use queues to be able to execute discord actions from child threads.
# https://stackoverflow.com/a/67996748

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from random import shuffle

from discord.colour import Colour
from discord.ext import tasks
from discord.member import Member
from discord.utils import escape_markdown

import discord_bots.config as config
from .bot import bot
from .commands import (
    add_player_to_queue,
    is_in_game,
)
from .log import define_logger
from .models import (
    InProgressGame,
    InProgressGameChannel,
    MapVote,
    Player,
    Queue,
    QueuePlayer,
    QueueWaitlist,
    QueueWaitlistPlayer,
    Session,
    SkipMapVote,
    VotePassedWaitlist,
    VotePassedWaitlistPlayer,
    Map,
)
from .queues import AddPlayerQueueMessage, add_player_queue
from .utils import send_message, update_current_map_to_next_map_in_rotation, get_current_map_readonly

log = define_logger(__name__)


@tasks.loop(minutes=1)
async def afk_timer_task():
    try:
        with Session() as session:
            channel = bot.get_channel(config.CHANNEL_ID)
            timeout = datetime.now(timezone.utc) - timedelta(minutes=config.AFK_TIME_MINUTES)

            player: Player
            for player in (
                    session.query(Player)
                            .join(QueuePlayer)
                            .filter(Player.last_activity_at < timeout, QueuePlayer.player_id == Player.id)
            ):
                queue_player = (
                    session.query(QueuePlayer)
                    .filter(QueuePlayer.player_id == player.id)
                    .first()
                )
                if queue_player:
                    member: Member | None = channel.guild.get_member(player.id)
                    # TODO if not a member, send without mention (likely left the server)
                    if member:
                        await send_message(
                            channel,
                            content=member.mention,
                            embed_content=False,
                            embed_description=f"{escape_markdown(player.name)} was removed from all queues for being inactive for {config.AFK_TIME_MINUTES} minutes",
                            colour=Colour.red(),
                        )
                    session.query(QueuePlayer).filter(
                        QueuePlayer.player_id == player.id
                    ).delete()
                    session.commit()

            votes_removed_sent = False
            for player in (
                    session.query(Player)
                            .join(MapVote)
                            .filter(Player.last_activity_at < timeout, MapVote.player_id == Player.id)
            ):
                map_votes: list[MapVote] = (
                    session.query(MapVote).filter(MapVote.player_id == player.id).all()
                )
                if len(map_votes) > 0:
                    member: Member | None = channel.guild.get_member(player.id)
                    if member:
                        await send_message(
                            channel,
                            content=member.mention,
                            embed_content=False,
                            embed_description=f"{escape_markdown(player.name)}'s votes removed for being inactive for {config.AFK_TIME_MINUTES} minutes",
                            colour=Colour.red(),
                        )
                        votes_removed_sent = True
                    session.query(MapVote).filter(MapVote.player_id == player.id).delete()
                    session.commit()

            for player in (
                    session.query(Player)
                            .join(SkipMapVote)
                            .filter(Player.last_activity_at < timeout, SkipMapVote.player_id == Player.id)
            ):
                skip_map_votes: list[SkipMapVote] = (
                    session.query(SkipMapVote).filter(SkipMapVote.player_id == player.id).all()
                )
                if len(skip_map_votes) > 0:
                    # So we don't send this message twice
                    if not votes_removed_sent:
                        member: Member | None = channel.guild.get_member(player.id)
                        if member:
                            await send_message(
                                channel,
                                content=member.mention,
                                embed_content=False,
                                embed_description=f"{escape_markdown(player.name)}'s votes removed for being inactive for {config.AFK_TIME_MINUTES} minutes",
                                colour=Colour.red(),
                            )
                    session.query(SkipMapVote).filter(
                        SkipMapVote.player_id == player.id
                    ).delete()
                    session.commit()
    except Exception:
        log.exception("Error in scheduled task")


@tasks.loop(seconds=1)
async def queue_waitlist_task():
    """
    Move players in the waitlist into the queues. Pop queues if needed.

    This exists as a task so that it happens on the main thread. Sqlite doesn't
    like to do writes on a second thread.

    TODO: Tests for this method
    """
    try:
        with Session() as session:
            queues: list[Queue] = session.query(Queue).order_by(Queue.created_at.asc())  # type: ignore
            queue_waitlist: QueueWaitlist
            for queue_waitlist in session.query(QueueWaitlist).filter(
                    QueueWaitlist.end_waitlist_at < datetime.now(timezone.utc)
            ):
                queue_waitlist_players: list[QueueWaitlistPlayer]
                queue_waitlist_players = (
                    session.query(QueueWaitlistPlayer)
                    .filter(QueueWaitlistPlayer.queue_waitlist_id == queue_waitlist.id)
                    .all()
                )
                qwp_by_queue_id: dict[str, list[QueueWaitlistPlayer]] = defaultdict(list)
                for qwp in queue_waitlist_players:
                    if qwp.queue_id:
                        qwp_by_queue_id[qwp.queue_id].append(qwp)

                # Ensure that we process the queues in the order the queues were created
                for queue in queues:
                    qwps_for_queue = qwp_by_queue_id[queue.id]
                    shuffle(qwps_for_queue)
                    for queue_waitlist_player in qwps_for_queue:
                        if is_in_game(queue_waitlist_player.player_id):
                            session.delete(queue_waitlist_player)
                            continue

                        player = session.query(Player).filter(Player.id == queue_waitlist_player.player_id).first()

                        add_player_queue.put(
                            AddPlayerQueueMessage(
                                queue_waitlist_player.player_id,
                                player.name,
                                # TODO: This is sucky to do it one at a time
                                [queue.id],
                                False
                            )
                        )
                for igp_channel in session.query(InProgressGameChannel).filter(
                        InProgressGameChannel.in_progress_game_id
                        == queue_waitlist.in_progress_game_id
                ):
                    voice_channel = bot.get_channel(igp_channel.channel_id)
                    if voice_channel:
                        await voice_channel.delete()
                    session.delete(igp_channel)
                session.query(QueueWaitlistPlayer).filter(
                    QueueWaitlistPlayer.queue_waitlist_id == queue_waitlist.id
                ).delete()
                session.delete(queue_waitlist)
                session.query(InProgressGame).filter(
                    InProgressGame.id == queue_waitlist.in_progress_game_id
                ).delete()
            session.commit()
    except Exception:
        log.exception("Error in scheduled task")


@tasks.loop(seconds=1)
async def vote_passed_waitlist_task():
    """
    Move players in the waitlist into the queues. Pop queues if needed.

    This exists as a task so that it happens on the main thread. Sqlite doesn't
    like to do writes on a second thread.

    TODO: Tests for this method
    """
    try:
        with Session() as session:
            vpw: VotePassedWaitlist | None = (
                session.query(VotePassedWaitlist)
                .filter(VotePassedWaitlist.end_waitlist_at < datetime.now(timezone.utc))
                .first()
            )
            if not vpw:
                return

            queues: list[Queue] = session.query(Queue).order_by(Queue.created_at.asc())  # type: ignore

            # TODO: Do we actually need to filter by id?
            vote_passed_waitlist_players: list[VotePassedWaitlistPlayer] = (
                session.query(VotePassedWaitlistPlayer)
                .filter(VotePassedWaitlistPlayer.vote_passed_waitlist_id == vpw.id)
                .all()
            )
            vpwp_by_queue_id: dict[str, list[VotePassedWaitlistPlayer]] = defaultdict(list)
            for vote_passed_waitlist_player in vote_passed_waitlist_players:
                vpwp_by_queue_id[vote_passed_waitlist_player.queue_id].append(
                    vote_passed_waitlist_player
                )

            # Ensure that we process the queues in the order the queues were created
            for queue in queues:
                vpwps_for_queue = vpwp_by_queue_id[queue.id]
                shuffle(vpwps_for_queue)
                for vote_passed_waitlist_player in vpwps_for_queue:
                    if is_in_game(vote_passed_waitlist_player.player_id):
                        session.delete(vote_passed_waitlist_player)
                        continue

                    player = session.query(Player).filter(Player.id == vote_passed_waitlist_player.player_id).first()

                    add_player_queue.put(
                        AddPlayerQueueMessage(
                            vote_passed_waitlist_player.player_id,
                            player.name,
                            # TODO: This is sucky to do it one at a time
                            [queue.id],
                            False
                        )
                    )

            session.query(VotePassedWaitlistPlayer).filter(
                VotePassedWaitlistPlayer.vote_passed_waitlist_id == vpw.id
            ).delete()
            session.delete(vpw)
            session.commit()
    except Exception:
        log.exception("Error in scheduled task")


@tasks.loop(minutes=1)
async def map_rotation_task():
    """
    Rotate the map automatically, stopping on the 0th map
    """
    try:
        current_map, current_map_full = get_current_map_readonly()
        if current_map and not config.RANDOM_MAP_ROTATION:
            with Session() as session:
                first_rotation_map: Map = session.query(Map).filter(Map.rotation_weight > 0).order_by(
                    Map.rotation_index.asc()).first()  # type: ignore
                if first_rotation_map and current_map_full.rotation_index == first_rotation_map.rotation_index:
                    # Stop at the first rotation map
                    return

        if not current_map:
            await update_current_map_to_next_map_in_rotation()
        else:
            time_since_update: timedelta = datetime.now(
                timezone.utc
            ) - current_map.updated_at.replace(tzinfo=timezone.utc)
            if (time_since_update.seconds // 60) > config.MAP_ROTATION_MINUTES:
                await update_current_map_to_next_map_in_rotation()
    except Exception:
        log.exception("Error in scheduled task")


@tasks.loop(seconds=1)
async def add_player_task():
    """
    Handle adding players in a task that pulls messages off of a queue.

    This helps with concurrency issues since players can be added from multiple
    sources (waitlist vs normal add command)
    """
    try:
        with Session() as session:
            queues: list[Queue] = session.query(Queue).all()
            queue_by_id: dict[str, Queue] = {queue.id: queue for queue in queues}
            while not add_player_queue.empty():
                queues_added_to: list[str] = []
                message: AddPlayerQueueMessage = add_player_queue.get()
                queue_popped = False
                queue_ids = message.queue_ids.copy()
                if config.POP_RANDOM_QUEUE:
                    shuffle(queue_ids)
                for queue_id in queue_ids:
                    queue: Queue = queue_by_id[queue_id]
                    if queue.is_locked:
                        continue

                    added_to_queue, queue_popped = await add_player_to_queue(queue.id, message.player_id)
                    if queue_popped:
                        break
                    if added_to_queue:
                        queues_added_to.append(queue.name)

                if not queue_popped and message.should_print_status:
                    queue_statuses = []
                    queue: Queue
                    for queue in queues:
                        queue_players = (
                            session
                            .query(QueuePlayer)
                            .filter(QueuePlayer.queue_id == queue.id)
                            .all()
                        )

                        in_progress_games: list[InProgressGame] = (
                            session.query(InProgressGame)
                            .filter(InProgressGame.queue_id == queue.id)
                            .all()
                        )

                        if len(in_progress_games) > 0:
                            queue_statuses.append(
                                f"{queue.name} [{len(queue_players)}/{queue.size}] *(In game)*"
                            )
                        else:
                            queue_statuses.append(
                                f"{queue.name} [{len(queue_players)}/{queue.size}]"
                            )

                    channel = bot.get_channel(config.CHANNEL_ID)
                    await send_message(
                        channel,
                        content=f"{message.player_name} added to: {', '.join(queues_added_to)}",
                        embed_description=" ".join(queue_statuses),
                        colour=Colour.green(),
                    )
    except Exception:
        log.exception("Error in scheduled task")
