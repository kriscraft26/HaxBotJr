from typing import List
from math import ceil, trunc

from discord import Embed

from wynnapi import WynnData
from util.discordutil import Discord
from state.guildmember import GuildMember
from state.statistic import Statistic


COLOR_ERROR = 0xfe5e41
COLOR_WARNING = 0xf7b32b
COLOR_INFO = 0x306bac
COLOR_SUCCESS = 0x8fb339

MAX_ENTRY_PER_PAGE = 10


def make_alert(text, title="", subtext=None, color: int=COLOR_ERROR) -> Embed:
    embed = Embed(title=text, color=color)
    embed.set_author(name=title)
    subtext and embed.set_footer(text=subtext)
    return embed


def decorate_text(text, sh="haskell", title=None, info=None, 
        api=None, lastUpdate=None) -> str:
    text = text.strip()
    if api:
        text = f"{text}\n\nUpdated {api.getLastUpdateDTime().seconds}s ago."
    elif lastUpdate:
        text = f"{text}\n\nLast updated at {lastUpdate}."
    if info:
        text = f"{info}\n\n{text}"
    if title:
        text = f"◀ {title} ▶\n\n{text}"
    return f"```{sh}\n{text}\n```"


def slice_entries(entries: List[str], maxEntries=MAX_ENTRY_PER_PAGE) -> List[List[str]]:
    pages = []
    buffer = entries[:]

    while len(buffer) > maxEntries:
        pages.append(buffer[:maxEntries])
        buffer = buffer[maxEntries:]
    pages.append(buffer)

    return pages


def make_page_indicator(pageNum, pageIndex) -> str:
    return "○ " * pageIndex + "● " + "○ " * (pageNum - pageIndex - 1)


def make_entry_pages(entries, maxEntries=MAX_ENTRY_PER_PAGE, **decoArgs):
    pages = slice_entries(entries, maxEntries=maxEntries)
    pageNum = len(pages)

    pageFmt = lambda _: "\n".join(_[1]) + "\n\n" + make_page_indicator(pageNum, _[0])
    return list(map(lambda _: decorate_text(pageFmt(_), **decoArgs), enumerate(pages)))


async def make_stat_entries(valGetter, nameGetter=None, group=True, filter_=None, rank=True,
                            lb=None):
    nameGetter = nameGetter or (lambda m: m.ign)
    data = []
    maxNameLen = -1

    if lb:
        members = map(GuildMember.members.get, lb)
        for member in (filter(filter_, members) if filter_ else members):
            name = nameGetter(member)
            maxNameLen = max(maxNameLen, len(name))
            data.append((name, valGetter(member)))
    else:
        with GuildMember.members:
            async for member in GuildMember.members.avalues(filter_):
                val = valGetter(member)
                name = nameGetter(member)
                maxNameLen = max(maxNameLen, len(name))
                data.append((name, val))

    entryFmt = "%s{:<%d}  |  {:%s}" % (
        "[{:<%d}]  " % len(str(len(data))) if rank else "", maxNameLen, "," if group else "")

    entries = []
    for i, (name, val) in enumerate(data):
        entries.append(entryFmt.format(*((i + 1, name, val) if rank else (name, val))))
    return entries


def make_member_title(member):
    if member.ownerId:
        return GuildMember.members[member.ownerId].ign + " " + member.ign
    elif member.discordId:
        return str(Discord.guild.get_member(member.discordId)) + " " + member.ign
    else:
        return member.ign


def format_act_dt(dt):
    days = dt.days
    seconds = trunc(dt.seconds)
    hours = seconds // 3600
    minutes = seconds // 60 % 60
    seconds = seconds % 60

    return f"{days:02} {hours:02}:{minutes:02}:{seconds:02}"