from discord import Message
from discord.ext import commands

from logger import Logger
from util.cmdutil import parser
from util.timeutil import now
from msgmaker import *
from reactablemessage import ReactableMessage
from pagedmessage import PagedMessage
from confirmmessage import ConfirmMessage
from cog.datacog import DataCog
from cog.configuration import Configuration
from cog.membermanager import MemberManager


@DataCog.register("lastUpdateTimeStr")
class EmeraldTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.provider = None
        self.parseAlert: ReactableMessage = None
        self.lastUpdateTimeStr = "owo"

        self._config: Configuration = bot.get_cog("Configuration")
        self._memberManager: MemberManager= bot.get_cog("MemberManager")
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if not self.provider:
            return
        if message.author.id == self.provider.id:
            attachments = message.attachments
            if not attachments:
                return

            text = (await attachments[0].read()).decode("utf-8")
            try:
                self.parse_gu_list(text)
                self.lastUpdateTimeStr = now().strftime("%b %d, %H:%M:%S (UTC)")
                alert = make_alert("Successfully parsed!", color=COLOR_SUCCESS)

            except Exception as e:
                alert = make_alert(str(e), title="An error occurred while parsing")

            finally:
                await self.parseAlert.edit_message(embed=alert)
                await self.parseAlert.un_track()

                self.provider = None
                self.parseAlert = None

    def parse_gu_list(self, text: str):
        for line in text.split("\n"):
            if not line:
                continue
            sections = line.split(" - ")
            ign = sections[0].split(" ")[-1]
            if ign in self._memberManager.ignIdMap:
                member = self._memberManager.get_member_by_ign(ign)
                em = int(sections[2][:-1])
                Logger.em.info(f"{ign} em update {member.emerald} -> {em}")
                member.emerald = em
                self._memberManager.rank_emerald(member.id)
    
    def reset_em(self):
        Logger.em.info("Resetting all emeralds")
        for member in self._memberManager.members.values():
            member.emerald = 0

    @parser("em", isGroup=True)
    async def display_emerald(self, ctx: commands.Context):
        lb = self._memberManager.emeraldLb
        igns = self._memberManager.ignIdMap.keys()
        members = self._memberManager.members
        statSelector = lambda m: m.emerald
        title = "Emerald Contribution Leader Board"
        
        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title, lastUpdate=self.lastUpdateTimeStr)
        await PagedMessage(pages, ctx.channel).init()

    @parser("em parse", parent=display_emerald)
    async def start_parse(self, ctx: commands.Context):
        if not await self._config.group_check(ctx, "trusted"):
            return

        if self.provider:
            alert = make_alert(f"Already an existing parse action by {self.provider}")
            await ctx.send(alert)
            return

        text = "Your next uploaded file will be parsed"
        subtext = "react with ❌ to cancel this action"
        alert = make_alert(text, subtext=subtext, color=COLOR_INFO)

        msg = ReactableMessage(ctx.channel)
        msg._init_send = lambda: ctx.send(embed=alert)
        msg.add_callback("❌", self.parse_cancel_cb, provideSelf=True)

        self.provider = ctx.author
        self.parseAlert = msg
        await msg.init()
    
    async def parse_cancel_cb(self, msg: ReactableMessage):
        self.provider = None
        self.parseAlert = None

        alert = make_alert("Action canceled", color=COLOR_SUCCESS)
        await msg.edit_message(embed=alert)
        await msg.un_track()
    
    @parser("em reset", parent=display_emerald)
    async def reset_em_cmd(self, ctx: commands.Context):
        if not await self._config.group_check(ctx, "staff"):
            return
        
        text = "Are you sure to reset all members' emerald?"
        successText = "Successfully reset all members' emerald."

        await ConfirmMessage(ctx, text, successText, lambda msg: self.reset_em()).init()