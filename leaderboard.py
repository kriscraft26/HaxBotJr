from typing import List, Dict, Tuple

from logger import LoggerPair, Logger
from msgmaker import make_entry_pages, make_stat_entries
from cog.datamanager import DataManager


@DataManager.register("_stats", "_acc", "_bw", "_total", "_totalLb", "_accLb", "_bwLb",
                      idFunc=lambda lb: lb.name)
class LeaderBoard:

    _instances = {}
    _memberManager = None

    def __init__(self, name, logger):
        self.name = name
        self._logger: LoggerPair = logger

        self._stats = {}
        self._acc = {}
        self._bw = {}
        self._total = {}

        self._totalLb = []
        self._accLb = []
        self._bwLb = []

        LeaderBoard._instances[name] = self
    
    @classmethod
    def set_member_manager(cls, memberManager):
        cls._memberManager = memberManager
    
    @classmethod
    def get_lb(cls, name: str):
        return cls._instances[name]
    
    @classmethod
    def get_entry(cls, id_: int) -> Dict[str, Tuple[int, int]]:
        entry = {}
        for lb in cls._instances.values():
            name = lb.name
            entry[name] = (lb.get_stat(id_), 0)
            entry[f"{name}Acc"] = (lb.get_acc(id_), lb.get_acc_rank(id_))
            entry[f"{name}Bw"] = (lb.get_bw(id_), lb.get_bw_rank(id_))
            entry[f"{name}Total"] = (lb.get_total(id_), lb.get_total_rank(id_))
        return entry
    
    @classmethod
    def remove_entry(cls, id_: int):
        for lb in cls._instances.values():
            lb.remove_id(id_)
    
    @classmethod
    def force_add_entry(cls, id_: int, entry: Dict[str, Tuple[int, int]]):
        for lb in cls._instances.values():
            name = lb.name

            stat = entry[name][0]
            acc = entry[name + "Acc"][0]
            bw = entry[name + "Bw"][0]
            total = entry[name + "Total"][0]

            lb._stats[id_] = stat
            if acc:
                lb._acc[id_] = acc
            if bw:
                lb._bw[id_] = bw
            if total:
                lb._total[id_] = total

            lb._update_lb(id_)
    
    @classmethod
    def reset_all_bw(cls):
        for lb in cls._instances.values():
            lb.reset_bw()
    
    @classmethod
    def reset_all_acc(cls, id_: int):
        for lb in cls._instances.values():
            lb.reset_acc(id_)

    @classmethod
    def init_lb(cls, idSet):
        for lb in cls._instances.values():
            lb._totalLb = sorted(idSet, key=lambda id_: -lb.get_total(id_))
            lb._accLb = sorted(idSet, key=lambda id_: -lb.get_acc(id_))
            lb._bwLb = sorted(idSet, key=lambda id_: -lb.get_bw(id_))

    @classmethod
    def _get_ign(cls, id_: int):
        return cls._memberManager.members[id_].ign
    
    def set_stat(self, id_: int, val: int):
        prev = self.get_stat(id_)
        diff = val - prev
        ign = LeaderBoard._get_ign(id_)

        if id_ not in self._stats:
            if diff:
                self._logger.info(f"{ign} {self.name} -> {val}")
                self._stats[id_] = val
            self._update_lb(id_)
            return

        if diff > 0:
            self._acc[id_] = self.get_acc(id_) + diff
            self._bw[id_] = self.get_bw(id_) + diff
            self._total[id_] = self.get_total(id_) + diff
            self._update_lb(id_)
        
        if diff:
            self._logger.info(f"{ign} {self.name} {self.get_stat(id_)} -> {val}")

            self._stats[id_] = val

        return diff
    
    def remove_id(self, id_: int):
        if id_ in self._stats:
            del self._stats[id_]
            self._acc.pop(id_, 0)
            self._bw.pop(id_, 0)
            self._total.pop(id_, 0)

            self._accLb.remove(id_)
            self._bwLb.remove(id_)
            self._totalLb.remove(id_)
    
    def reset_acc(self, id_: int):
        self._acc.pop(id_, 0)
    
    def reset_bw(self):
        self._bw = {}

    def get_stat(self, id_: int):
        return self._get_val(id_, self._stats)
    
    def get_total(self, id_: int):
        return self._get_val(id_, self._total)
    
    def get_total_rank(self, id_: int):
        return self._get_rank(id_, self._totalLb)
    
    def get_acc(self, id_: int):
        return self._get_val(id_, self._acc)
    
    def get_acc_rank(self, id_: int):
        return self._get_rank(id_, self._accLb)
    
    def get_bw(self, id_: int):
        return self._get_val(id_, self._bw)
    
    def get_bw_rank(self, id_: int):
        return self._get_rank(id_, self._bwLb)
    
    def _get_val(self, id_: int, valMap):
        return valMap.get(id_, 0)
    
    def _get_rank(self, id_: int, lb):
        if id_ not in lb:
            return 0
        return lb.index(id_) + 1
    
    def _update_lb(self, id_: int):
        self._rank(id_, self._accLb, self.get_acc)
        self._rank(id_, self._bwLb, self.get_bw)
        self._rank(id_, self._totalLb, self.get_total)
    
    def _rank(self, id_: int, lb: List[int], key):
        if id_ in lb:
            lb.remove(id_)
        val = key(id_)

        # A binary search algorithm
        # since it is not searching for a specific value, so the edge case
        # of not finding a value is not considered.

        left = 0
        right = len(lb) - 1

        end = False
        while not end:
            # Edge case when stat is the smallest
            if left > right:
                mid = left
                break
            mid = left + (right - left) // 2
            
            # check if the ordering is correct, both left and right side
            # if both are correct, the possition for stat is found
            lCondition = True if mid == 0 else key(lb[mid - 1]) >= val
            rCondition = val >= key(lb[mid])

            # if the array is already ordered from big to small
            # at least one of the condition is true 
            if lCondition and rCondition:
                end = True
            elif lCondition:
                left = mid + 1
            elif rCondition:
                right = mid
            else:
                self._re_rank_all(lb, key)
                return
        
        lb.insert(mid, id_)
    
    def _re_rank_all(self, lb: List[int], key):
        lb.clear()
        for id_ in self._stats:
            self._rank(id_, lb, key)
    
    def create_pages(self, acc: bool, total: bool, **decoArgs) -> List[str]:
        if acc:
            lb = self._accLb
            ss = self.get_acc
            header = "Accumulated "
        elif total:
            lb = self._totalLb
            ss = self.get_total
            header = "Total "
        else:
            lb = self._bwLb
            ss = self.get_bw
            header = "Bi-Weekly "
        
        igns = LeaderBoard._memberManager.get_igns_set()
        members = LeaderBoard._memberManager.members
        if "title" in decoArgs:
            decoArgs["title"] = header + decoArgs["title"]
        
        return make_entry_pages(make_stat_entries(lb, igns, members, lambda m: ss(m.id)),
            **decoArgs)