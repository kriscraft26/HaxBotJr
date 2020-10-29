import pickle
import os

class Data(dict):

    def __init__(self, name):
        super().__init__()
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


config = Data("Configuration")
config.data = config.data["_config"]
del config.data["channel.expedition"]
del config.data["role.expedition"]
del config.data["user.ignore"]
del config.data["vrole.visual"]
del config.data["vrole.personal"]
config.rename({name: name.replace(".", "_") for name in config.data})
config.save(newName="Config")