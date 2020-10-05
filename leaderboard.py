from logger import LoggerPair, Logger
from msgmaker import make_entry_pages, make_stat_entries
from cog.datamanager import DataManager


@DataManager.register("_lb", "_stats", idFunc=lambda lb: lb.name,
                      mapper={"lb": "_lb", "stats": "_stats"})
class LeaderBoard:

    _instances = {}
    _memberManager = None
    
    def __init__(self, name: str, logger: LoggerPair):
        self.name = name
        self._lb = []
        self._stats = {}
        self._logger = logger

        LeaderBoard._instances[name] = self
    
    def __loaded__(self):
        if not self._stats:
            return
        sampleStat = list(self._stats.values())[0]
        if type(sampleStat) != int:
            Logger.bot.debug("Outdated format detected, updating...")
            for id_ in self._stats:
                self._stats[id_] = self._stats[id_].val
            Logger.bot.debug(f"-> {self._stats}")
    
    @classmethod
    def set_member_manager(cls, memberManager):
        cls._memberManager = memberManager

    @classmethod
    def get_lb(cls, lbName: str):
        return cls._instances[lbName]
    
    @classmethod
    def get_ign(cls, id_: int):
        if not cls._memberManager:
            return str(id_)
        return cls._memberManager.members[id_].ign
    
    @classmethod
    def remove_stats(cls, id_: int):
        for lb in cls._instances.values():
            lb.remove_stat(id_)
    
    @classmethod
    def get_stats(cls, id_: int):
        return {lb.name: lb.get_stat(id_) for lb in cls._instances.values()}
    
    @classmethod
    def get_ranks(cls, id_: int):
        return {lb.name: lb.get_rank(id_) for lb in cls._instances.values()}
    
    @classmethod
    def accumulate(cls, id_: int, statName: str, newTotal: int):
        totalLb: LeaderBoard = cls.get_lb(f"{statName}Total")
        accLb: LeaderBoard = cls.get_lb(f"{statName}Acc")
        
        if id_ not in totalLb._lb:
            totalLb.set_stat(id_, newTotal)
            accLb.set_stat(id_, 0)
            return

        prevTotal = totalLb.get_stat(id_)
        prevAcc = accLb.get_stat(id_)
    
        delta = newTotal - prevTotal

        if delta < 0:
            ign = LeaderBoard.get_ign(id_)
            accLb._logger.warning(
                f"{ign} total xp decreased {prevTotal} -> {newTotal}")
        elif delta > 0:
            accLb.set_stat(id_, prevAcc + delta)
        
        if delta != 0:
            totalLb.set_stat(id_, newTotal)
        
    def set_stat(self, id_: int, val: int):
        ign = LeaderBoard.get_ign(id_)
        self._logger.info(f"{ign} {self.name} {self.get_stat(id_)} -> {val}")
        self._stats[id_] = val
        self._rank_stat(id_)
    
    def reset_stats(self):
        for id_ in self._stats:
            self.set_stat(id_, 0)
    
    def get_stat(self, id_: int):
        return self._stats.get(id_, 0)
    
    def remove_stat(self, id_: int):
        self._stats.pop(id_, -1)
        id_ in self._lb and self._lb.remove(id_)
    
    def _rank_stat(self, id_: int):
        if id_ in self._lb:
            self._lb.remove(id_)
        val = self._stats[id_]

        # A binary search algorithm
        # since it is not searching for a specific value, so the edge case
        # of not finding a value is not considered.

        left = 0
        right = len(self._lb) - 1

        end = False
        while not end:
            # Edge case when stat is the smallest
            if left > right:
                mid = left
                break
            mid = left + (right - left) // 2
            
            # check if the ordering is correct, both left and right side
            # if both are correct, the possition for stat is found
            lCondition = True if mid == 0 else self._stats[self._lb[mid - 1]] >= val
            rCondition = val >= self._stats[self._lb[mid]]

            # if the array is already ordered from big to small
            # at least one of the condition is true 
            if lCondition and rCondition:
                end = True
            elif lCondition:
                left = mid + 1
            elif rCondition:
                right = mid
            else:
                self._re_rank_all()
                return
        
        self._lb.insert(mid, id_)
    
    def _re_rank_all(self):
        self._lb.clear()
        for id_ in self._stats:
            self._rank_stat(id_)
    
    def get_rank(self, id_: int) -> int:
        if id_ not in self._lb:
            return 0
        return self._lb.index(id_)
    
    def get_max(self) -> int:
        return max(self._stats.items())
    
    def get_total(self) -> int:
        return sum(self._stats.items())
    
    def get_average(self) -> float:
        return self.get_total() / len(self._lb)
    
    def create_pages(self, **decoArgs):
        igns = LeaderBoard._memberManager.ignIdMap.keys()
        members = LeaderBoard._memberManager.members
        statSelector = lambda m: self.get_stat(m.id)
        return make_entry_pages(make_stat_entries(
            self._lb, igns, members, statSelector), **decoArgs)