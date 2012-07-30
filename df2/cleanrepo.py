import build
import jssort
import os

UI_STRINGS_EN = ["src", "ui-strings", "ui_strings-en.js"]

def normws(src):
    for root, dirs, files in os.walk(src):
        for name in files:
            if name.endswith(".js"):
                lines = None
                path = os.path.join(root, name)
                with open(path, "rb") as f:
                    lines = f.readlines()
                if lines:
                    c = "\n".join(map(lambda s: s.rstrip(), lines)) + "\n"
                    if not c == "".join(lines):
                        with open(path, "wb") as f:
                            f.write(c)
                            print "fixed", path

def cleanrepo(args):
    if not os.path.exists(os.path.join(*UI_STRINGS_EN)):
        print "you must run the tool in the root of a Dragonfly repo."
        return

    print "run jssort"
    args.src = os.path.join(*UI_STRINGS_EN)
    jssort.jssort(args)
    print "run fixBOM"
    args.src = UI_STRINGS_EN[0]
    build.fix_bom(args)
    print "run normws"
    normws(UI_STRINGS_EN[0])

def setup_subparser(subparsers, config):
    subp = subparsers.add_parser("cleanrepo", help="""Runs jssort, fixBOM and normws.
                                                      Must be run in the root of a
                                                      Dragonfly repo""")
    subp.set_defaults(func=cleanrepo)
