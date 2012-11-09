# To add a new command import a module which exposes a method
#
#    def setup_subparser(subparsers, config):
#
# All modules will be scanned for such a method.

import os
import sys
import argparse
import json
import js2db
import jssort
import po2js
import db2js
import verifyids
import showconfig
import build
import cleanrepo
import normws
import codegen.msgdefs
import codegen.jsclasses
import codegen.scopedoc

SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))

def deep_update(target, src):
    for key in src.keys():
        if type(src[key]) == type({}):
            if not key in target:
                target[key] = {}
            deep_update(target[key], src[key])
        else:
            target[key] = src[key]

def get_config():
    config = {}
    with open(os.path.join(SOURCE_ROOT, "DEFAULTS"), "r") as f:
        config.update(json.loads(f.read()))
    home = os.environ.get('HOME') or os.environ.get('HOMEPATH')
    if home:
        for name in ['df2.ini', '.df2', 'DF2', 'df2.cfg']:
            path = os.path.abspath(os.path.join(home, name))
            if os.path.isfile(path):
                with open(path, "r") as f:
                    deep_update(config, json.loads(f.read()))
                break
    return config

def main():
    description = """Tool collection to build Opera Dragonfly and handle
    language strings. The tool uses an optional configuration file in the home
    directory ("df2.ini", ".df2", "DF2" or "df2.cfg"). Use 'df2 configdoc'
    to see all options."""

    parser = argparse.ArgumentParser(prog='df2', description=description)
    config=get_config()
    parser.set_defaults(config=config)
    parser.set_defaults(root_path=SOURCE_ROOT)
    subparsers = parser.add_subparsers()
    candidates = globals().values()
    candidates.extend((getattr(codegen, name)  for name in dir(codegen)))
    for module in candidates:
        try: getattr(module, "setup_subparser")(subparsers, config)
        except AttributeError: pass
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
