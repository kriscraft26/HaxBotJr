import pickle
import os


class PickleUtil:
    

    @staticmethod
    def save(path, data):
        with open(path, "wb") as file:
            pickle.dump(data, file, pickle.HIGHEST_PROTOCOL)
    

    @staticmethod
    def load(path, initData=None):
        if not os.path.isfile(path):
            PickleUtil.save(path, initData)
            return initData

        obj = None
        with open(path, "rb") as file:
            obj = pickle.load(file)
        return obj