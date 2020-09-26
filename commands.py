from util.messageUtil import *
from util.cmdUtil import parser
from tracker.XPTracker import XPTracker
from PurgeManager import PurgeManager
from pagedmessage import PagedMessage
from GuildMember import GuildMember
from Config import config


commandPrefix = "]"
parser.commandPrefix = commandPrefix


@parser("xp", ["total"])
async def xp(ctx, total):
    title = ("Total" if total else "Accumulated Bi-Weekly") + " Contributed XP Leaderboard"
    statSelector = lambda m: m.getTotalXp() if total else m.getAccXp()

    with GuildMember.lbLock:
        lb = GuildMember.totalXpLb if total else GuildMember.accXpLb
    pages = createLbPages(lb, statSelector, "guildStats", title)
    await PagedMessage(pages, ctx.channel).init()


@parser("wc")
async def wc(ctx):
    title = "Accumulated Bi-Weekly War Count Leaderboard"
    statSelector = lambda m: m.getWarCount()

    with GuildMember.lbLock:
        lb = GuildMember.warCountLb
    pages = createLbPages(lb, statSelector, "serverList", title)
    await PagedMessage(pages, ctx.channel).init()


@parser("wl", isGroup=True)
async def wl(ctx):
    title = "White List"
    content = "[Permenant]\n" + ", ".join(PurgeManager.wlPerm) \
        + "\n\n[Temporary]\n" + ", ".join(PurgeManager.wlTemp)
    await ctx.send(wrapMessage(title, content, None))


@parser("wl add", "names...", ["perm"], parent=wl)
async def wl_add(ctx, names, perm):
    names = set(filter(lambda s: s, names))
    wlNames = PurgeManager.wlPerm.union(PurgeManager.wlTemp)
    # filter for non guild member names
    with GuildMember.membersLock:
        otherNames = names.difference(set(GuildMember.ignIdMap.keys()))
    names = names.difference(otherNames)
    # filter for already listed names
    inListNames = names.intersection(wlNames)
    names = names.difference(inListNames)

    errorReason = "as they aren't guild member or already listed"

    if not names:
        text = f"no names are added, {errorReason}."
        await displayError(ctx.channel, text, None)
        return
    
    PurgeManager.addNames(names, perm)
    
    skippedNames = otherNames.union(inListNames)
    if otherNames:
        text = f"{len(skippedNames)} names are skipped. {errorReason}."
        subtext = f"added {', '.join(names)} and skipped {', '.join(skippedNames)}"
        await displayWarning(ctx.channel, text, subtext)
    else:
        text = f"added {len(names)} names to the white list"
        subtext = f"added {', '.join(names)}"
        await displaySuccess(ctx.channel, text, subtext)


@parser("wl remove", "names...", ["perm"], parent=wl)
async def wl_remove(ctx, names, perm):
    names = set(filter(lambda s: s, names))
    wlNames = PurgeManager.wlPerm if perm else PurgeManager.wlTemp
    # filter for unlisted names
    unlistedNames = names.difference(wlNames)
    names = names.difference(unlistedNames)

    errorReason = f"as they are unlisted on {'permenant' if perm else 'temporary'} list"

    if not names:
        text = f"no names are removed, {errorReason}."
        await displayError(ctx.channel, text, None)
        return

    PurgeManager.removeNames(names, perm)
    
    if unlistedNames:
        text = f"{len(unlistedNames)} names are skipped, {errorReason}."
        subtext = f"removed {', '.join(names)} and skipped {', '.join(unlistedNames)}"
        await displayWarning(ctx.channel, text, subtext)
    else:
        text = f"successfully removed {len(names)} names from the white list"
        subtext = f"removed {', '.join(names)}"
        await displaySuccess(ctx.channel, text, subtext)


@parser("wl clear", ["perm"], parent=wl)
async def wl_clear(ctx, perm):
    PurgeManager.clearWhitelist(perm)

    text = f"successfully cleared {'permenant' if perm else 'temporary'} white list"
    await displaySuccess(ctx.channel, text, None)


@parser("stat", "name", ["removed"])
async def stat(ctx, name, removed):
    if removed:
        with GuildMember.removedMembersLock:
            for member in GuildMember.removedMembers.values():
                if member.getIgn() == name:
                    await displayMember(ctx.channel, member, config.guild)
                    return
        await displayError(ctx.channel, f"{name} is not a removed guild member", None)
        return

    with GuildMember.membersLock:
        if name in GuildMember.ignIdMap:
            await displayMember(
                ctx.channel, GuildMember.members[GuildMember.ignIdMap[name]], config.guild)
        else:
            await displayError(ctx.channel, f"{name} is not a guild member", None)


@parser("members", ["removed"])
async def members(ctx, removed):
    if removed:
        with GuildMember.removedMembersLock:
            lb = GuildMember.removedMembers.values()
        if not lb:
            await displayError(ctx.channel, "No removed members", None)
            return
    else:
        with GuildMember.membersLock:
            lb = GuildMember.members.keys()
    title = "Removed Guild Members" if removed else "Guild Members"
    pages = createLbPages(lb, lambda m: m.getRank(), None, title, rawMembers=removed)
    await PagedMessage(pages, ctx.channel).init()


@parser("config")
async def config_(ctx):
    with config.lock:
        await displayDict(ctx.channel, config.config)