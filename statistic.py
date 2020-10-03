from logger import LoggerPair
from msgmaker import make_entry_pages, make_stat_entries
from cog.datamanager import DataManager


class Statistic:

    def __init__(self, name: str, id_: int, initVal: int=-1):
        self.name = name
        self.lb: LeaderBoard = LeaderBoard.get_lb(name)
        self.id = id_
        super().__setattr__("val", initVal)
        self.lb.add_stat(self)
    
    def __reduce__(self):
        return (self.__class__, (self.name, self.id, self.val))

    def __repr__(self):
        return f"<Statistic {self.name}={self.val}>"
    
    def __setattr__(self, name, value):
        prevVal = getattr(self, name, None)
        super().__setattr__(name, value)
        if name == "val":
            self.lb.log_change(prevVal, self)
            self.lb.rank_stat(self)


class AccumulatedStatistic:

    def __init__(self, name: str, id_: int, resetRange: int = 1000):
        self.total = Statistic(f"{name}Total", id_)
        self.acc = Statistic(f"{name}Acc", id_, initVal=0)
        self.resetRange = resetRange
    
    def accumulate(self, newTotal: int):
        if self.total.val == -1:
            self.total.val = newTotal
            return

        delta = newTotal - self.total.val
        isResetDetected = False

        if delta < 0:
            if newTotal <= self.resetRange:
                ign = self.acc.lb.get_ign(self.acc)
                self.acc.lb.logger.info(
                    f"{ign} xp reset detected {self.total.val} -> {newTotal}")
                self.acc.val += newTotal
                isResetDetected = True
        elif delta > 0:
            self.acc.val += delta
        
        if delta != 0:
            self.total.val = newTotal
        
        return isResetDetected
        
    def reset(self):
        self.acc.val = 0
    
    def __repr__(self):
        return f"<AccumulatedStatistic total={self.total.val} acc={self.acc.val}>"


@DataManager.register("lb", "stats", idFunc=lambda lb: lb.name)
class LeaderBoard:

    _instances = {}
    _memberManager = None
    
    def __init__(self, name: str, logger: LoggerPair):
        self.name = name
        self.lb = []
        self.stats = {}
        self.logger = logger

        LeaderBoard._instances[name] = self
    
    @classmethod
    def set_member_manager(cls, memberManager):
        cls._memberManager = memberManager

    @classmethod
    def get_lb(cls, lbName: str):
        return cls._instances[lbName]
    
    def get_ign(self, stat: Statistic):
        if not LeaderBoard._memberManager:
            return str(stat.id)
        return LeaderBoard._memberManager.members[stat.id].ign

    def log_change(self, prevVal: int, stat: Statistic):
        ign = self.get_ign(stat)
        self.logger.info(f"{ign} {stat.name} {prevVal} -> {stat.val}")

    def add_stat(self, stat: Statistic):
        self.stats[stat.id] = stat
        self.rank_stat(stat)
    
    def remove_stat(self, stat: Statistic):
        del self.stats[stat.id]
        self.lb.remove(stat.id)
    
    def rank_stat(self, stat: Statistic):
        id_ = stat.id
        if id_ in self.lb:
            self.lb.remove(id_)

        # A binary search algorithm
        # since it is not searching for a specific value, so the edge case
        # of not finding a value is not considered.

        left = 0
        right = len(self.lb) - 1

        end = False
        while not end:
            # Edge case when stat is the smallest
            if left > right:
                mid = left
                break
            mid = left + (right - left) // 2
            
            # check if the ordering is correct, both left and right side
            # if both are correct, the possition for stat is found
            lCondition = True if mid == 0 else self.stats[self.lb[mid - 1]].val >= stat.val
            rCondition = stat.val >= self.stats[self.lb[mid]].val

            # if the array is already ordered from big to small
            # at least one of the condition is true 
            if lCondition and rCondition:
                end = True
            elif lCondition:
                left = mid + 1
            elif rCondition:
                right = mid
            else:
                raise Exception("Bad array")
        
        self.lb.insert(mid, id_)
    
    def get_rank(self, id_: int) -> int:
        if id_ not in self.lb:
            return -1
        return self.lb.index(id_)
    
    def get_max(self) -> int:
        return max(self.stats.items())
    
    def get_total(self) -> int:
        return sum(self.stats.items())
    
    def get_average(self) -> float:
        return self.get_total() / len(self.lb)
    
    def create_pages(self, **decoArgs):
        igns = LeaderBoard._memberManager.ignIdMap.keys()
        members = LeaderBoard._memberManager.members
        statSelector = lambda m: self.stats[m.id].val
        return make_entry_pages(make_stat_entries(
            self.lb, igns, members, statSelector), **decoArgs)