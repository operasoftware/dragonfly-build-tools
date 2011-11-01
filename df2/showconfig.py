import sys
import json
import os

def showconfig(args):
	json.dump(args.config, sys.stdout, indent=1)

def configdoc(args):
	with open(os.path.join(args.root_path, "CONFIGDOC"), "r") as f:
		print f.read()

def setup_subparser(subparsers, config):
	subp = subparsers.add_parser('showconfig', help="Show the config file.")
	subp.set_defaults(func=showconfig)
	subp = subparsers.add_parser('configdoc', help="Show the config options.")
	subp.set_defaults(func=configdoc)
	