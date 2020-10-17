from argparse import ArgumentParser
from discord.ext import commands

from msgmaker import make_alert


class CatchableArgumentParser(ArgumentParser):

    def exit(self, status=0, message=None):
        if status:
            raise Exception(message)

"""
"arg"                       positional argument
["arg"]                     flag argument
"arg..."                    extend argument
["arg..."]                  flag extend argument
"-arg"                      flag argument
["arg", ("choice", ...)]    choice argument
[["arg"], ("choice", ...)]  flag choice argument
"arg*"                      optional positional argument
"""
def parser(name, *args, isGroup=False, parent=None, **destMap):
    argParser = CatchableArgumentParser(prog=f"]{name}", add_help=False)
    for arg in args:
        argType = type(arg)
        if argType == str:
            #  "arg..."
            if arg.endswith("..."):
                arg = arg[:-3]
                argParser.add_argument(
                    dest=destMap.pop(arg, arg), action="extend", nargs="+", type=str)
            #  "-arg"
            elif arg[0] == "-":
                arg = arg[1:]
                argParser.add_argument(
                    f"-{arg[0]}", f"--{arg}", action="store", dest=destMap.pop(arg, arg))
            elif arg[-1] == "*":
                arg = arg[:-1]
                argParser.add_argument(arg, nargs="*")
            #  "arg"
            else:
                argParser.add_argument(dest=destMap.pop(arg, arg))
        elif argType == list:
            #  ["arg"]
            if len(arg) == 1:
                arg = arg[0]
                if arg.endswith("..."):
                    arg = arg[:-3]
                    argParser.add_argument(f"-{arg[0]}", f"--{arg}", action="extend", 
                        nargs="+", type=str)
                else:
                    argParser.add_argument(f"-{arg[0]}", f"--{arg}", 
                        action="store_true", dest=destMap.pop(arg, arg))
            elif len(arg) == 2:
                [arg, choices] = arg
                #  ["arg", ("choice", ...)]
                if type(arg) == str:
                    argParser.add_argument(arg, choices=choices)
                #  [["arg"], ("choice", ...)]
                elif type(arg) == list:
                    arg = arg[0]
                    argParser.add_argument(f"-{arg[0]}", f"--{arg}", choices=choices,
                        dest=destMap.pop(arg, arg))
    def wrapper(func):
        p = parent if parent else commands
        funcName = name.split(" ")[-1]
        cmdWrapper = p.group(name=funcName, invoke_without_command=True) \
            if isGroup else p.command(name=funcName)
        @cmdWrapper
        async def parsable(self, ctx, *arguments):
            try:
                args = vars(argParser.parse_args(arguments))
            except Exception as e:
                await ctx.send(embed=make_alert(":".join(str(e).split(":")[2:])))
                return
            for cmdArgName, funcArgName in destMap.items():
                args[funcArgName] = args.pop(cmdArgName, None)
            await func(self, ctx, **args)
        return parsable
    return wrapper