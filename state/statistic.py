from datetime import timedelta
import bisect

from logger import Logger
from event import Event
from state.guildmember import GuildMember
from state.state import State


@State.register("stats")
class Statistic:

    stats = {}

    xpLb = []
    warLb = []
    emeraldLb = []

    xpTotalLb = []
    warTotalLb = []
    emeraldTotalLb = []
    
    onlineTimeLb = []
    onlineTimeBwLb = []

    @classmethod
    async def __loaded__(cls):
        ids = cls.stats.keys()
        cls.xpLb = sorted(ids, key=lambda id_: -cls.stats[id_].xp["biweek"])
        cls.xpTotalLb = sorted(ids, key=lambda id_: -cls.stats[id_].xp["total"])
        cls.warLb = sorted(ids, key=lambda id_: -cls.stats[id_].war["biweek"])
        cls.warTotalLb = sorted(ids, key=lambda id_: -cls.stats[id_].war["total"])
        cls.emeraldLb = sorted(ids, key=lambda id_: -cls.stats[id_].emerald["biweek"])
        cls.emeraldTotalLb = sorted(ids, key=lambda id_: -cls.stats[id_].emerald["total"])
        cls.onlineTimeLb = sorted(ids, key=lambda id_: -cls.stats[id_].onlineTime["curr"])
        cls.onlineTimeBwLb = sorted(ids, key=lambda id_: -cls.stats[id_].onlineTime["biweek"])

        Event.listen("memberAdd", cls._on_member_add)
        Event.listen("memberStatusChange", cls._on_member_status_change)

    @classmethod
    def reset_biweekly(cls):
        for stat in cls.stats.values():
            stat._reset_biweekly()

    @classmethod
    def _update_lb(cls, lb, id_, attr, field):
        lb.remove(id_)

        lo = 0
        hi = len(lb)
        val = getattr(cls.stats[id_], attr)[field]

        while lo < hi:
            mid = (lo + hi) // 2
            if val > getattr(cls.stats[lb[mid]], attr)[field]:
                hi = mid
            else:
                lo = mid + 1

        lb.insert(lo, id_)

    @classmethod
    async def _on_member_add(cls, id_):
        if id_ not in cls.stats:
            cls.stats[id_] = Statistic(id_)

            cls.xpLb.append(id_)
            cls.xpTotalLb.append(id_)
            cls.warLb.append(id_)
            cls.warTotalLb.append(id_)
            cls.emeraldLb.append(id_)
            cls.emeraldTotalLb.append(id_)
            cls.onlineTimeLb.append(id_)
            cls.onlineTimeBwLb.append(id_)
    
    @classmethod
    async def _on_member_status_change(cls, id_, prevStatus):
        if GuildMember.members[id_].status != GuildMember.ACTIVE:
            await cls.stats[id_].update_world(None)

    def __init__(self, id_):
        self.id = id_

        self.xp = Statistic.ContributionAccumulator()
        self.war = Statistic.Accumulator("biweek", "total")
        self.emerald = Statistic.ContributionAccumulator()
        self.onlineTime = Statistic.Accumulator("biweek", "curr", valType=timedelta)

        self.world = None
    
    def __repr__(self):
        s = "<Statistic"
        properties = ["xp", "war", "emerald", "onlineTime", "world"]
        for p in properties:
            if hasattr(self, p):
                s += f" {p}={getattr(self, p)}"
        return s + ">"

    async def update_xp(self, val):
        return await self._update_contribution("xp", val)
    
    async def update_emerald(self, val):
        return await self._update_contribution("emerald", val)
    
    async def _update_contribution(self, name, val):
        accumulator = getattr(self, name)

        prev = self.xp.real
        diff = self.xp.update(val)
        if diff:
            Statistic._update_lb(Statistic.xpLb, self.id, name, "biweek")
            Statistic._update_lb(Statistic.xpTotalLb, self.id, name, "total")

            ign = GuildMember.members[self.id].ign
            Logger.bot.info(f"{ign} {name} {prev} -> {self.xp.real}")
            await Event.broadcast(name + "Change", self.id, diff)
        return diff
    
    async def increment_war(self):
        self.war.accumulate(1)
        Statistic._update_lb(self.warLb, self.id, "war", "biweek")
        Statistic._update_lb(self.warTotalLb, self.id, "war", "total")

        ign = GuildMember.members[self.id].ign
        Logger.bot.info(f"{ign} war count incremented to {self.war['total']}")
        await Event.broadcast("warIncrement", self.id)
    
    async def update_world(self, newWorld):
        if newWorld != self.world:
            prev = self.world
            self.world = newWorld
            await Event.broadcast("worldChange", self.id, prev)
            if newWorld is None:
                prev = self.onlineTime["curr"]
                self.onlineTime.reset_entry("curr")
                Statistic.onlineTimeLb.remove(self.id)
                Statistic.onlineTimeLb.append(self.id)

                await Event.broadcast("offline", self.id, prev)
    
    async def accumulate_online_time(self, dt):
        self.onlineTime.accumulate(dt)

        Statistic._update_lb(Statistic.onlineTimeLb, self.id, "onlineTime", "curr")
        Statistic._update_lb(Statistic.onlineTimeBwLb, self.id, "onlineTime", "biweek")

        await Event.broadcast("onlineTimeAccumulate", self.id, dt)
    
    def _reset_biweekly(self):
        self.xp.reset_entry("biweek")
        self.war.reset_entry("biweek")
        self.emerald.reset_entry("biweek")
        self.onlineTime.reset_entry("biweek")

    class Accumulator:

        def __init__(self, *entries, valType=int):
            self.entries = {entry: valType() for entry in entries}
            self.valType = valType
        
        def __getitem__(self, entry):
            return self.entries[entry]
        
        def __repr__(self):
            s = "<Accumulator"
            for e, v in self.entries.items():
                s += f" {e}={v}"
            return s + ">"
        
        def accumulate(self, diff):
            for entry in self.entries:
                self.entries[entry] += diff
        
        def reset_entry(self, entry):
            self.entries[entry] = self.valType()
    
    class ContributionAccumulator(Accumulator):

        def __init__(self):
            super().__init__("total", "biweek")
            self.real = None
        
        def __repr__(self):
            s = "<Accumulator"
            s += f" real={self.real}"
            for e, v in self.entries.items():
                s += f" {e}={v}"
            return s + ">"
        
        def update(self, newReal):
            prevReal = self.real
            self.real = newReal
            if prevReal is None:
                self.entries["total"] = newReal
                return 0

            diff = newReal - prevReal
            if diff:
                if diff < 0:
                    diff = newReal
                
                if diff > 0:
                    self.accumulate(diff)

            return diff