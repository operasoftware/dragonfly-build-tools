import os
import sys
import argparse
import json
import js2db
import po2js
import db2js
import verifyids
import showconfig
import build

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
	directory ("df2.ini", ".df2", "DF2" or "df2.cfg"). Use 'df2 configformat' 
	to see all options."""

	parser = argparse.ArgumentParser(prog='df2', description=description)
	config=get_config()
	#print config.get("build").get("default_profile")
	parser.set_defaults(config=config)
	parser.set_defaults(root_path=SOURCE_ROOT)
	subparsers = parser.add_subparsers()
	g = globals()
	for name in g:
		module = g.get(name)
		if hasattr(module, "setup_subparser"):
			getattr(module, "setup_subparser")(subparsers, config)

	args = parser.parse_args()
	args.func(args)

if __name__ == '__main__':
	main()