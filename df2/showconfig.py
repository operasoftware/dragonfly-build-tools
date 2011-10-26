import sys
import json

def showconfig(args):
	json.dump(args.config, sys.stdout, indent=1)

def setup_subparser(subparsers, config):
	subp = subparsers.add_parser('showconfig', help="Show the config file.")
	subp.set_defaults(func=showconfig)