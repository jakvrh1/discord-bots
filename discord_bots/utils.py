# Misc helper functions
import itertools
import math
import os
import statistics
from datetime import datetime, timezone
from random import choice

import discord
import imgkit
from PIL import Image
from discord import Colour, DMChannel, Embed, GroupChannel, TextChannel
from discord.ext.commands.context import Context
from trueskill import Rating, global_env

from discord_bots.bot import bot
from discord_bots.config import CHANNEL_ID, STATS_DIR, STATS_HEIGHT, STATS_WIDTH, RANDOM_MAP_ROTATION
from discord_bots.log import define_logger
from discord_bots.models import (
    CurrentMap,
    Map,
    MapVote,
    Player,
    Session,
    SkipMapVote,
)

log = define_logger(__name__)


def is_really_numeric(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False


def get_current_map_readonly() -> tuple[CurrentMap, Map] | tuple[None, None]:
    """
    !WARNING! The objects are no longer tracked by the session. Treat them as immutable.
    :return:
    """
    with Session() as session:
        current_map: CurrentMap | None = session.query(CurrentMap).first()
        if current_map:
            current_map_full: Map = session.query(Map).join(CurrentMap).filter(CurrentMap.map_id == Map.id).first()
            return current_map, current_map_full
        else:
            return None, None


# Convenience mean function that can handle lists of 0 or 1 length
def mean(values: list[any]) -> float:
    if len(values) == 0:
        return -1
    else:
        return statistics.mean(values)


def pretty_format_team(
        team_name: str, win_probability: float, players: list[Player]
) -> str:
    player_names = ", ".join(sorted([player.name for player in players]))
    return f"**{team_name}** ({round(100 * win_probability, 1)}%): {player_names}\n"


def short_uuid(uuid: str) -> str:
    return uuid.split("-")[0]


async def send_message(
        channel: (DMChannel | GroupChannel | TextChannel),
        content: str | None = None,
        embed_description: str | None = None,
        colour: Colour | None = None,
        embed_content: bool = True,
        embed_title: str | None = None,
        embed_thumbnail: str | None = None,
):
    """
    :colour: red = fail, green = success, blue = informational
    """
    if content:
        if embed_content:
            content = f"`{content}`"
    embed = None
    if embed_title or embed_thumbnail or embed_description or colour:
        embed = Embed()
    if embed_title:
        embed.title = embed_title
    if embed_thumbnail:
        embed.set_thumbnail(url=embed_thumbnail)
    if embed_description:
        embed.description = embed_description
    if colour:
        embed.colour = colour
    try:
        await channel.send(content=content, embed=embed)
    except Exception as e:
        log.error(f"Error sending message: {e}\n"
                  f"\tcontent: {content}\n"
                  f"\tembed_title: {embed_title}\n"
                  f"\tembed_description: {embed_description}\n"
                  f"\tembed_thumbnail: {embed_thumbnail}\n"
                  f"\tcolour: {colour}"
                  f"\tchannel: {channel}")


async def update_current_map_to_next_map_in_rotation():
    with Session() as session:
        current_map, current_map_full = get_current_map_readonly()
        current_map_id = current_map.map_id if current_map else 'DUMMY'
        current_rotation_index = current_map_full.rotation_index if current_map_full else -1

        rotation_maps: list[Map] = session.query(Map).filter(Map.rotation_weight > 0,
                                                             Map.id != current_map_id).order_by(
            Map.rotation_index.asc()).all()  # type: ignore
        if len(rotation_maps) > 0:
            if RANDOM_MAP_ROTATION:
                next_map = choice(rotation_maps)
                while next_map.id == current_map_id:
                    next_map = choice(rotation_maps)
            else:
                next_map = next(filter(lambda x: x.rotation_index > current_rotation_index, rotation_maps), None) or \
                           rotation_maps[0]

            update_current_map(next_map.id)

            session.query(MapVote).delete()
            session.query(SkipMapVote).delete()
            session.commit()
            channel = bot.get_channel(CHANNEL_ID)
            if isinstance(channel, discord.TextChannel):
                await send_message(
                    channel,
                    embed_description=f"Map automatically rotated to **{next_map.full_name}**, all votes removed",
                    colour=discord.Colour.blue(),
                )


async def upload_stats_screenshot_imgkit(ctx: Context, cleanup=True):
    # Assume the most recently modified HTML file is the correct stat sheet
    if not STATS_DIR:
        return

    html_files = list(filter(lambda x: x.endswith(".html"), os.listdir(STATS_DIR)))
    html_files.sort(key=lambda x: os.path.getmtime(os.path.join(STATS_DIR, x)), reverse=True)

    if len(html_files) == 0:
        return

    image_path = os.path.join(STATS_DIR, html_files[0] + ".png")
    imgkit.from_file(os.path.join(STATS_DIR, html_files[0]), image_path, options={"enable-local-file-access": None})
    if STATS_WIDTH and STATS_HEIGHT:
        image = Image.open(image_path)
        # TODO: Un-hardcode these
        cropped = image.crop((0, 0, STATS_WIDTH, STATS_HEIGHT))
        cropped.save(image_path)

    await ctx.message.channel.send(file=discord.File(image_path))

    # Clean up everything
    if cleanup:
        for file_ in os.listdir(STATS_DIR):
            if file_.endswith(".png") or file_.endswith(".html"):
                os.remove(os.path.join(STATS_DIR, file_))


def win_probability(team0: list[Rating], team1: list[Rating]) -> float:
    """
    Calculate the probability that team0 beats team1
    Taken from https://trueskill.org/#win-probability
    """
    BETA = 4.1666
    delta_mu = sum(r.mu for r in team0) - sum(r.mu for r in team1)
    sum_sigma = sum(r.sigma ** 2 for r in itertools.chain(team0, team1))
    size = len(team0) + len(team1)
    denom = math.sqrt(size * (BETA * BETA) + sum_sigma)
    trueskill = global_env()

    return trueskill.cdf(delta_mu / denom)


def update_current_map(map_id: str) -> None:
    with Session() as session:
        current_map: CurrentMap | None = session.query(CurrentMap).first()
        if current_map:
            current_map.map_id = map_id
            current_map.updated_at = datetime.now(timezone.utc)
        else:
            session.add(CurrentMap(map_id))
        session.commit()
