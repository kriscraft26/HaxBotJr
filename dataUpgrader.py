import pickle
import os
from pprint import pformat
import datetime

from state.guildmember import GuildMember
from state.statistic import Statistic


class Data:

    def __init__(self, name):
        self.path = f"./data/{name}.data"
        with open(self.path, "rb") as file:
            self.data: dict = pickle.load(file)
    
    def save(self, newName=None):
        if newName:
            self.path = f"./data/{newName}.data"
        with open(self.path, "wb") as file:
            pickle.dump(self.data, file, pickle.HIGHEST_PROTOCOL)
    
    def rename(self, nameMap):
        for old, new in nameMap.items():
            self.data[new] = self.data.pop(old)


emLb = Data("LeaderBoard.emerald")
warLb = Data("LeaderBoard.warCount")
xpLb = Data("LeaderBoard.xp")
act = Data("ActivityTracker")
members = Data("GuildMember").data["members"]

stats = {}


def sync_contribution(id_, lb, accumulator):
    real = lb.data["_stats"].get(id_, 0)
    total = lb.data["_total"].get(id_, 0)
    bw = lb.data["_bw"].get(id_, 0)

    accumulator.real = real
    accumulator.entries["total"] = max(real, total)
    accumulator.entries["biweek"] = bw


for m in members.values():
    if m.status != "removed":
        stat = Statistic(m.id)
        sync_contribution(m.id, xpLb, stat.xp)
        sync_contribution(m.id, emLb, stat.emerald)

        stat.war.entries["total"] = warLb.data["_stats"].get(m.id, 0)
        stat.war.entries["biweek"] = warLb.data["_bw"].get(m.id, 0)

        [total, curr, _, world] = act.data["activities"][m.id]
        stat.onlineTime.entries["total"] = total
        stat.onlineTime.entries["curr"] = curr
        stat.world = world

        stats[m.id] = stat

with open("./data/Statistic.data", "wb") as file:
    pickle.dump({"stats": stats}, file, pickle.HIGHEST_PROTOCOL)