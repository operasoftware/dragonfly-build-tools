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
					user_config = json.loads(f.read())
					for section in user_config:
						config.get(section, {}).update(user_config.get(section))
				break
	return config
	
def main():

	parser = argparse.ArgumentParser(prog='df2',
	                                 description='''Tool collection to build
	                                                Opera Dragonfly and handle  
	                                                language strings.''')
	config=get_config()
	#print config.get("build").get("default_profile")
	parser.set_defaults(config=config)
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