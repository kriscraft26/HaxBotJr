from typing import List
from math import ceil

from discord import Embed

from cog.wynnapi import WynnData


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
        api: WynnData.Tracker=None) -> str:
    if api:
        text = f"{text}\n\nUpdated {api.getLastUpdateDTime().seconds}s ago."
    if info:
        text = f"{info}\n\n{text}"
    if title:
        text = f"◀ {title} ▶\n\n{text}"
    return f"```{sh}\n{text}\n```"


def slice_entries(entries: List[str]) -> List[List[str]]:
    pages = []
    buffer = entries[:]

    while len(buffer) > MAX_ENTRY_PER_PAGE:
        pages.append(buffer[:MAX_ENTRY_PER_PAGE])
        buffer = buffer[MAX_ENTRY_PER_PAGE:]
    pages.append(buffer)

    return pages


def make_page_indicator(pageNum, pageIndex) -> str:
    return "○ " * pageIndex + "● " + "○ " * (pageNum - pageIndex - 1)


def make_lb_pages(ctx, lb, stateSelector, memberManager, **decorateArgs):
    entries = []

    maxIgnLen = max(map(len, memberManager.ignIdMap))
    maxRankLen = len(str(len(lb)))

    entryFormat = f"[%-{maxRankLen}d]  %-{maxIgnLen}s  |  %s"

    for rank, id_ in enumerate(lb):
        gMember = memberManager.members[id_]
        entries.append(entryFormat % (rank + 1, gMember.ign, stateSelector(gMember)))
    
    pages = []
    pageNum = ceil(len(lb) / MAX_ENTRY_PER_PAGE) 

    for index, pageEntries in enumerate(slice_entries(entries)):
        page = "\n".join(pageEntries) + "\n\n" + make_page_indicator(pageNum, index)
        pages.append(decorate_text(page, **decorateArgs))
    
    return pages