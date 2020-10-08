import os

dirName = os.path.dirname( __file__)
dataFiles = [os.path.join(dirName, f) for f in os.listdir(dirName)]

for file in dataFiles:
    if os.path.isfile(file) and not file.endswith(".py"):
        print(f"removing {file}")
        os.remove(file)