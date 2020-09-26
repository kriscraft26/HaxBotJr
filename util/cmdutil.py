from argparse import ArgumentParser
from discord.ext import commands


class CatchableArgumentParser(ArgumentParser):

    def exit(self, status=0, message=None):
        if status:
            raise Exception(message)

"""
"arg"       positional argument
["arg"]     flag argument
"arg..."    greedy argument
"""
def parser(name, *args, isGroup=False, parent=None):
    argParser = CatchableArgumentParser(prog=f"]{name}")
    for arg in args:
        argType = type(arg)
        if argType == str:
            if arg.endswith("..."):
                arg = arg[:-3]
                argParser.add_argument(dest=arg, action="extend", nargs="+", type=str)
            else:
                argParser.add_argument(dest=arg)
        elif argType == list:
            arg = arg[0]
            argParser.add_argument(f"-{arg[0]}", f"--{arg}", action="store_true", dest=arg)
    def wrapper(func):
        p = parent if parent else commands
        funcName = name.split(" ")[-1]
        cmdWrapper = p.group(name=funcName, invoke_without_command=True) \
            if isGroup else p.command(name=funcName)
        @cmdWrapper
        async def parsable(self, ctx, *arguments):
            await func(self, ctx, **vars(argParser.parse_args(arguments)))
        return parsable
    return wrapper