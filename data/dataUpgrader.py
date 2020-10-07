import pickle
import os

def save(path, data):
    with open(path, "wb") as file:
        pickle.dump(data, file, pickle.HIGHEST_PROTOCOL)


def load(path, initData=None):
    if not os.path.isfile(path):
        save(path, initData)
        return initData

    obj = None
    with open(path, "rb") as file:
        obj = pickle.load(file)
    return obj


emAccLb = load("./LeaderBoard.emeraldAcc.data")
emTotalLb = load("./LeaderBoard.emeraldTotal.data")

wcLb = load("./LeaderBoard.warCount.data")

xpAccLb = load("./LeaderBoard.xpAcc.data")
xpTotalLb = load("./LeaderBoard.xpTotal.data")


stats = {id_: val for id_, val in emTotalLb["_stats"].items() if val != -1}
rankBase = {id_: val - emAccLb["_stats"][id_] for id_, val in stats.items()}
emData = {
    "_stats": stats,
    "_statLb": emTotalLb["_lb"][:],
    "_rankBase": rankBase.copy(),
    "_accLb": emAccLb["_lb"][:],
    "_bwBase": rankBase.copy(),
    "_bwLb": emAccLb["_lb"][:]
}
save("./LeaderBoard.emerald.data", emData)


stats = {id_: val for id_, val in xpTotalLb["_stats"].items() if val != -1}
rankBase = {id_: val - xpAccLb["_stats"][id_] for id_, val in stats.items()}
xpData = {
    "_stats": stats,
    "_statLb": xpTotalLb["_lb"][:],
    "_rankBase": rankBase.copy(),
    "_accLb": xpAccLb["_lb"][:],
    "_bwBase": rankBase.copy(),
    "_bwLb": xpAccLb["_lb"][:]
}
save("./LeaderBoard.xp.data", xpData)


stats = {id_: val for id_, val in wcLb["_stats"].items() if val != -1}
rankBase = {id_: 0 for id_ in stats}
accLb = list(stats.keys())
wcData = {
    "_stats": stats,
    "_statLb": wcLb["_lb"][:],
    "_rankBase": rankBase.copy(),
    "_accLb": accLb[:],
    "_bwBase": rankBase.copy(),
    "_bwLb": accLb[:]
}
save("./LeaderBoard.warCount.data", wcData)