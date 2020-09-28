from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from pagedmessage import PagedMessage
from util.cmdutil import parser
from cog.wynnapi import WynnAPI
from cog.membermanager import MemberManager, GuildMember


XP_UPDATE_INTERVAL = 6

class XPTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        
        self._memberManager: MemberManager = bot.get_cog("MemberManager")

        self._update.start()

    @tasks.loop(seconds=XP_UPDATE_INTERVAL)
    async def _update(self):
        guildStats = self._guildStatsTracker.getData()
        if guildStats:
            for memberData in guildStats["members"]:
                if memberData["name"] in self._memberManager.ignIdMap:
                    gMember = self._memberManager.get_member_by_ign(memberData["name"])
                    self._update_member_xp(gMember, memberData["contributed"])
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting xp tracking loop")
    
    def _update_member_xp(self, member: GuildMember, currTXp: int):
        prevAccXp = member.accXp
        if currTXp > member.totalXp and member.totalXp >= 0:
            deltaXp = currTXp - member.totalXp
            member.accXp += deltaXp
            Logger.xp.info(f"{member.ign} +{deltaXp}xp, accXp {prevAccXp} -> {member.accXp}")
        elif currTXp < member.totalXp:
            # if the total xp decreased, then the member must have
            # left the guild before for it to be reset to 0.
            member.accXp = currTXp
            Logger.xp.info(f"{member.ign} xp resetted, accXp {prevAccXp} -> {member.accXp}")
        if currTXp != member.totalXp:
            Logger.xp.info(f"{member.ign} totalXp {member.totalXp} -> {currTXp}")
            member.totalXp = currTXp

            self._memberManager.rank_acc_xp(member.id)
            self._memberManager.rank_total_xp(member.id)
        
    def reset_xp(self):
        Logger.bot.info("resetting all accumulated xp.")
        for member in self._memberManager.members.values():
            member.accXp = 0
    
    @parser("xp", ["total"], isGroup=True)
    async def display_xp_lb(self, ctx: commands.Context, total):
        lb = self._memberManager.totalXpLb if total else self._memberManager.accXpLb
        igns = self._memberManager.ignIdMap.keys()
        members = self._memberManager.members
        title = ("Total XP " if total else "Accumulated XP ") + "Leader Board"
        statSelector = lambda m: m.totalXp if total else m.accXp

        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title, api=self._guildStatsTracker)
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("xp reset", parent=display_xp_lb)
    async def reset_xp_cmd(self, ctx: commands.Context):
        self.reset_xp()