import pickle
import os
from pprint import pformat
import datetime


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


memberManager = Data("MemberManager")
members = memberManager.data["members"].copy()
for k, m in memberManager.data["members"].items():
    if not hasattr(m, "mcId"):
        continue
    members[m.mcId] = m
    del members[k]
    m.discordId = m.id
    m.id = m.mcId
    del m.mcId
    del m.discord
    isIdle = k in memberManager.data["idleMembers"]
    m.status = "idle" if isIdle else "active"
    m.ownerId = None
memberManager.data = {"members": members}
discordIdMap = {members[id_].discordId: id_ for id_ in members}
memberManager.save(newName="GuildMember")


actTracker = Data("ActivityTracker")
val = actTracker.data["activities"]
newVal = {}
for dId, id_ in discordIdMap.items():
    if dId in val:
        newVal[id_] = val[dId]
    else:
        newVal[id_] = [datetime.timedelta(0), datetime.timedelta(0), False, None]
actTracker.data["activities"] = newVal
actTracker.save()


def updateLb(name):
    lb = Data("LeaderBoard." + name)
    for field, val in lb.data.items():
        if field.endswith("Lb"):
            newVal = list(map(discordIdMap.get, val))
        else:
            newVal = {discordIdMap[dId]: v for dId, v in val.items()}
        lb.data[field] = newVal
    lb.save()

updateLb("xp")
updateLb("emerald")
updateLb("warCount")