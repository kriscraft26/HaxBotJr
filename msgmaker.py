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


def make_stat_entries(lb, igns, members, statSelector):
    maxIgnLen = max(map(len, igns)) if igns else 0
    entryFmt = f"[%-{len(str(len(lb)))}d]  %-{maxIgnLen}s  |  %s"

    entries = []
    for i, id_ in enumerate(lb):
        gMember = members[id_]
        entries.append(entryFmt % (i + 1, gMember.ign, statSelector(gMember)))
    return entries