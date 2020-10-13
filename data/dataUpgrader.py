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


config = load("./data/Configuration.data")
config["_config"]["vrole.visual"] = config["_config"]["role.visual"]
del config["_config"]["role.visual"]
config["_config"]["vrole.personal"] = config["_config"]["role.personal"]
del config["_config"]["role.personal"]

save("./data/Configuration.data", config)