from typing import List, Dict, Tuple

from logger import LoggerPair, Logger
from msgmaker import make_entry_pages, make_stat_entries
from cog.datamanager import DataManager


@DataManager.register("_bwBase", "_rankBase", "_stats", "_statLb", "_accLb", "_bwLb",
                      idFunc=lambda lb: lb.name)
class LeaderBoard:

    _instances = {}
    _memberManager = None

    def __init__(self, name, logger):
        self.name = name
        self._logger: LoggerPair = logger

        self._bwBase = {}
        self._rankBase = {}
        self._stats = {}

        self._statLb = []
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
            entry[name] = (lb.get_stat(id_), lb.get_stat_rank(id_))
            entry[f"{name}Acc"] = (lb.get_acc(id_), lb.get_acc_rank(id_))
            entry[f"{name}Bw"] = (lb.get_bw(id_), lb.get_bw_rank(id_))
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

            lb._stats[id_] = stat
            lb._rankBase[id_] = stat - acc
            lb._bwBase[id_] = stat - bw

            lb._rank_stat(id_)
            lb._rank_acc(id_)
            lb._rank_bw(id_)
    
    @classmethod
    def update_all_bw_base(cls):
        for lb in cls._instances.values():
            lb.update_bw_base()
    
    @classmethod
    def update_all_rank_base(cls, id_: int):
        for lb in cls._instances.values():
            lb.update_rank_base(id_)

    @classmethod
    def _get_ign(cls, id_: int):
        return cls._memberManager.members[id_].ign
    
    def set_stat(self, id_: int, val: int):
        prev = self.get_stat(id_)
        if prev != val:
            ign = LeaderBoard._get_ign(id_)
            self._logger.info(f"{ign} {self.name} {self.get_stat(id_)} -> {val}")

            self._stats[id_] = val
            if id_ not in self._rankBase:
                self._rankBase[id_] = val
                self._bwBase[id_] = val

            self._rank_stat(id_)
            self._rank_acc(id_)
            self._rank_bw(id_)
        return val - prev
    
    def remove_id(self, id_: int):
        if id_ in self._stats:
            del self._stats[id_]
            del self._rankBase[id_]
            del self._bwBase[id_]

            self._statLb.remove(id_)
            self._accLb.remove(id_)
            self._bwLb.remove(id_)
    
    def update_rank_base(self, id_: int):
        self._rankBase[id_] = self.get_stat(id_)
    
    def update_bw_base(self):
        self._bwBase = self._stats.copy()

    def get_stat(self, id_: int):
        return self._stats.get(id_, 0)
    
    def get_stat_rank(self, id_: int):
        if id_ not in self._statLb:
            return 0
        return self._statLb.index(id_) + 1
    
    def get_acc(self, id_: int):
        return self.get_stat(id_) - self._rankBase.get(id_, 0)
    
    def get_acc_rank(self, id_: int):
        if id_ not in self._accLb:
            return 0
        return self._accLb.index(id_) + 1
    
    def get_bw(self, id_: int):
        return self.get_stat(id_) - self._bwBase.get(id_, 0)
    
    def get_bw_rank(self, id_: int):
        if id_ not in self._bwLb:
            return 0
        return self._bwLb.index(id_) + 1
    
    def _rank_stat(self, id_: int):
        self._rank(id_, self._statLb, self.get_stat)
    
    def _rank_acc(self, id_: int):
        self._rank(id_, self._accLb, self.get_acc)
    
    def _rank_bw(self, id_: int):
        self._rank(id_, self._bwLb, self.get_bw)
    
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
    
    def create_pages(self, acc: bool, bw: bool, **decoArgs) -> List[str]:
        if acc:
            lb = self._accLb
            ss = self.get_acc
            header = "Accumulated "
        elif bw:
            lb = self._bwLb
            ss = self.get_bw
            header = "Bi-Weekly "
        else:
            lb = self._statLb
            ss = self.get_stat
            header = ""
        
        igns = LeaderBoard._memberManager.get_igns_set()
        members = LeaderBoard._memberManager.members
        if "title" in decoArgs:
            decoArgs["title"] = header + decoArgs["title"]
        
        return make_entry_pages(make_stat_entries(lb, igns, members, lambda m: ss(m.id)),
            **decoArgs)