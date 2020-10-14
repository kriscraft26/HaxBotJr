from datetime import datetime, timedelta
from math import trunc

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import *
from reactablemessage import PagedMessage
from util.timeutil import now, add_tz_info
from util.cmdutil import parser
from cog.datamanager import DataManager
from cog.wynnapi import WynnAPI
from cog.configuration import Configuration


CLAIM_UPDATE_INTERVAL = 6
CLAIM_ALERT_DElAY = 5  # in minutes


@DataManager.register("_claims")
class ClaimTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self._claims = {}
        self._claimNameOrder = []
        self._allTerrs = set()

        self._config: Configuration = bot.get_cog("Configuration")
        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._terrListTracker = wynnAPI.terrList.get_tracker()

        self._hasInitClaimUpdate = False
        self._shouldAlert = False

        self.bot = bot
    
    def __loaded__(self):
        self._claimNameOrder = list(self._claims.keys())
        self._order_claim_names()

        self._claim_update.start()

    @tasks.loop(seconds=CLAIM_UPDATE_INTERVAL)
    async def _claim_update(self):
        claimList = self._terrListTracker.getData()
        if not claimList:
            return
        claimList = claimList["territories"]

        if not self._hasInitClaimUpdate:
            self._allTerrs = set(claimList.keys())
            self._hasInitClaimUpdate = True
        
        isClaimAttacked = False
        isClaimReclaimed = False
        
        for claim in self._claims:
            prevGuild = self._claims[claim]["guild"]
            currGuild = claimList[claim]["guild"]
            isClaimAttacked = currGuild != "HackForums"
            self._claims[claim]["guild"] = currGuild
            if prevGuild != currGuild:
                if currGuild == "HackForums":
                    emoji = "🛡️"
                    isClaimReclaimed = True
                elif prevGuild == "HackForums":
                    emoji = "⚔️"
                else:
                    emoji = "🏹"
                text = f"{emoji} **{claim}**  __{prevGuild}__  ->  __{currGuild}__"
                await self._config.send("claimLog", text)

            acquired = self._parse_acquired(claimList[claim]["acquired"])
            self._claims[claim]["acquired"] = acquired
        
        self._order_claim_names()

        if isClaimAttacked and not isClaimReclaimed:
            if not self.bot.get_cog("WarTracker").currentWar:
                self.schedule_alert()
                return
        self.dismiss_alert()
    
    @_claim_update.before_loop
    async def _before_claim_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("starting claim update loop")
    
    def schedule_alert(self):
        if self._config("role.claimAlert") and not self._shouldAlert:
            self._alert.start()
    
    def dismiss_alert(self):
        if self._shouldAlert:
            self._shouldAlert = False
            self._alert.stop()
    
    @tasks.loop(minutes=CLAIM_ALERT_DElAY)
    async def _alert(self):
        if not self._shouldAlert:
            self._shouldAlert = True
            return
        
        isMissing = lambda t: self._claims[t]["guild"] != "HackForums"
        missing = list(filter(isMissing, self._claimNameOrder))
        if missing:
            roleId = self._config('role.claimAlert')

            missingNum = len(missing)
            if missingNum == 1:
                text = f"⚠️  **1 claim is missing**  <@&{roleId}>"
            else:
                text = f"⚠️  **{len(missing)} claims are missing**>  <@&{roleId}>"

            entries = []
            maxTerrLen = max(map(len, missing))
            template = "[{0:02}] {1:%d}  |  {2:%d}" % (maxTerrLen, 14)

            for index, terr in enumerate(missing):
                dt = self._format_timedelta(now() - self._claims[terr]["acquired"])
                entry = template.format(index + 1, terr, dt)
                guild = self._claims[terr]["guild"]
                entries.append(template.format(index + 1, terr, dt) + f"  [{guild}]")
            
            text += "\n" + decorate_text("\n".join(entries))

            await self._config.send("claimAlert", text)
        self._shouldAlert = False
        self._alert.stop()
    
    def _parse_acquired(self, acquired):
        return add_tz_info(datetime.strptime(acquired, "%Y-%m-%d %H:%M:%S"))
    
    def _order_claim_names(self):
        self._claimNameOrder.sort(key=lambda c: self._claims[c]["acquired"], reverse=True)

    def _format_timedelta(self, dt: timedelta):
        seconds = trunc(dt.seconds)

        weeks = dt.days // 7
        days = dt.days % 7
        hours = seconds // 3600
        minutes = seconds // 60 % 60
        seconds = seconds % 60
        return f"{weeks:02}/{days:02} {hours:02}:{minutes:02}:{seconds:02}"

    @parser("claim", isGroup=True)
    async def display_claims(self, ctx: commands.Context):
        if not self._claims:
            await ctx.send(decorate_text("Empty"))
            return

        entries = []
        maxTerrLen = max(map(len, self._claimNameOrder))
        template = "[{0:02}] {1:%d}  |  {2:%d}" % (maxTerrLen, 14)

        for index, terr in enumerate(self._claimNameOrder):
            dt = self._format_timedelta(now() - self._claims[terr]["acquired"])
            entry = template.format(index + 1, terr, dt)
            guild = self._claims[terr]["guild"]
            if guild == "HackForums":
                entries.append("--" + entry)
            else:
                entries.append(f"––{entry}  [{guild}]")
        
        await ctx.send(decorate_text("\n".join(entries), 
            title="Claims", api=self._terrListTracker))
    
    @parser("claim add", "terrs...", parent=display_claims)
    async def add_claims(self, ctx: commands.Context, terrs):
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        terrs = set(terrs)
        validTerrs = terrs.intersection(self._allTerrs)

        if not validTerrs:
            await ctx.send(embed=make_alert("No terrs are added."))
            return

        for terr in validTerrs:
            self._claims[terr] = {
                "guild": "None",
                "acquired": now()
            }
            self._claimNameOrder.append(terr)
        self._order_claim_names
        
        invalidTerrs = terrs.difference(self._allTerrs)

        text = f"Successfully added {len(validTerrs)} territories as claims."
        subText = f"Ignored {len(invalidTerrs)} territories." if invalidTerrs else None
        await ctx.send(embed=make_alert(text, subtext=subText, color=COLOR_SUCCESS))
    
    @parser("claim remove", "terrs...", parent=display_claims)
    async def remove_claims(self, ctx: commands.Context, terrs):
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        terrs = set(terrs)
        validTerrs = terrs.intersection(set(self._claimNameOrder))

        if not validTerrs:
            await ctx.send(embed=make_alert("No terrs are removed."))
            return

        for terr in validTerrs:
            del self._claims[terr]
            self._claimNameOrder.remove(terr)
        
        invalidTerrs = terrs.difference(validTerrs)

        text = f"Successfully removed {len(validTerrs)} claims."
        subText = f"Ignored {len(invalidTerrs)} claims." if invalidTerrs else None
        await ctx.send(embed=make_alert(text, subtext=subText, color=COLOR_SUCCESS))
    
    async def get_alert_status(self, ctx: commands.Context):
        pass