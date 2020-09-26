import math
from discord import Embed
from queue import Queue

from pagedmessage import PagedMessage
from WynnAPI import WynnAPI
from tracker.XPTracker import XPTracker
from GuildMember import GuildMember
import util.timeutil as timeUtil


MAX_ENTRY_PER_PAGE = 10

EMBED_COLOR_ERROR = 0xfe5e41
EMBED_COLOR_WARNING = 0xf7b32b
EMBED_COLOR_SUCCESS = 0x8fb339


async def displayLb(channel, title, statSelector, apiDataName):
    with GuildMember.membersLock:
        statMap = {member.ign: statSelector(member) for member in GuildMember.members.values()}
    pages = createLbPages(statMap, apiDataName, title)

    p = PagedMessage(pages, channel)
    await p.init()


def createLbPages(lb, statSelector, apiDataName, title, rawMembers=False):
    pages = []

    if rawMembers:
        members = lb
    else:
        with GuildMember.membersLock:
            members = list(map(lambda id: GuildMember.members[id], lb))
    statMap = {m.getIgn(): statSelector(m) for m in members}

    entryStrings = []
    entryCount = 0

    maxOrdLen = len(str(len(lb)))
    maxNameLen = len(max(statMap, key=lambda item: len(item)))
    maxStatLen = len(str(max(statMap.values())))

    pageNum = math.ceil(len(lb) / MAX_ENTRY_PER_PAGE)

    entryTemplate = f"⌈%-{maxOrdLen}s⌋ %-{maxNameLen}s ┃ %{maxStatLen}s"

    for entryIndex, (name, stat) in enumerate(statMap.items()):
        order = str(entryIndex + 1)

        entryStrings.append(entryTemplate % (order, name, stat))
        entryCount += 1

        if (entryIndex + 1) % MAX_ENTRY_PER_PAGE == 0 or entryIndex == len(lb) - 1:
            content = "\n".join(entryStrings)
            entryStrings.clear()

            indexIndicator = createIndexIndicator(pageNum, len(pages))
            content += "\n\n" + indexIndicator

            pages.append(wrapMessage(title, content, apiDataName))
            entryCount = 0
    
    return pages


def createIndexIndicator(pageNum, pageIndex):
    return "○ " * pageIndex + "● " + "○ " * (pageNum - pageIndex - 1)


def wrapMessage(title, content, dataName):
    if dataName:
        now = timeUtil.now()
        lastUpdate = WynnAPI.getLastUpdateTime(dataName)
        lastUpdate = f"\n\nUpdated {now - lastUpdate} ago"
    else:
        lastUpdate = ""
    return f"```haskell\n◀ {title} ▶\n\n{content}{lastUpdate}```"


async def displayError(channel, text, subtext):
    embed = Embed(title=text, color=EMBED_COLOR_ERROR)
    embed.set_author(name="ERROR")
    subtext and embed.set_footer(text=subtext)
    await channel.send(embed=embed)


async def displayWarning(channel, text, subtext):
    embed = Embed(title=text, color=EMBED_COLOR_WARNING)
    embed.set_author(name="WARNING")
    subtext and embed.set_footer(text=subtext)
    await channel.send(embed=embed)


async def displaySuccess(channel, text, subtext):
    embed = Embed(title=text, color=EMBED_COLOR_SUCCESS)
    embed.set_author(name="SUCCESS")
    subtext and embed.set_footer(text=subtext)
    await channel.send(embed=embed)


async def displayMember(channel, member, guild):
    dMember = guild.get_member(member.id)
    embed = Embed(color=dMember.colour, description=f"*{dMember.nick}*")
    embed.set_author(name=dMember.name, icon_url=str(dMember.avatar_url))

    with GuildMember.lbLock:
        totalXpRank = GuildMember.totalXpLb.index(member.id) + 1
        accXpRank = GuildMember.accXpLb.index(member.id) + 1
        warCountRank = GuildMember.warCountLb.index(member.id) + 1

    embed.add_field(
        name=f"Total XP (#{totalXpRank})", value=member.getTotalXp(), inline=False)
    embed.add_field(
        name=f"Accumulated XP (#{accXpRank})", value=member.getAccXp(), inline=False)
    embed.add_field(
        name=f"Accumulated War Count (#{warCountRank})", value=member.getWarCount(),
        inline=False)
    await channel.send(embed=embed)