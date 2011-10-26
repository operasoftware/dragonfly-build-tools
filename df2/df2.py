import os
import sys
import argparse
import json

import js2db
from po2js import command_po2js, LANGS
from db2js import command_db2js
import verifyids
import showconfig

config = {
	"po2js": {
		"langs": ['be', 'bg', 'cs', 'da', 'de', 'el', 'en-GB', 'es-ES', 'es-LA', 
		          'et', 'fi', 'fr', 'fr-CA', 'fy', 'gd', 'hi', 'hr', 'hu', 'id',
		          'it', 'ja', 'ka', 'ko', 'lt', 'mk', 'nb', 'nl', 'nn', 'pl',
		          'pt', 'pt-BR', 'ro', 'ru', 'sk', 'sr', 'sv', 'ta', 'te', 'tr',
		          'uk', 'vi', 'zh-cn', 'zh-tw']
	}
}

def get_config():
	home = os.environ.get('HOME') or os.environ.get('HOMEPATH')
	if home:
		for name in ['df2.ini', '.df2', 'DF2', 'df2.cfg']:
			path = os.path.abspath(os.path.join(home, name))
			if os.path.isfile(path):
				with open(path, "r") as f:
					content = f.read()
					return json.loads(content)
	
	return config

"""
def showconfig(args):
	json.dump(args.config, sys.stdout, indent=1)
"""

def main():

	parser = argparse.ArgumentParser(prog='df2',
	                                 description='''Tool to handle Dragonfly 
	                                 language strings.''')

	parser.set_defaults(config=get_config())
	
	subparsers = parser.add_subparsers(help='The available commands.')

	# po2js
	parser_po2js = subparsers.add_parser('po2js',
	                                     help='''Covert .po files to .js files.
	                                     By default %s are converted. This can
	                                     be overwritten with a configuration 
	                                     file (dfstr.ini, .dfstr, DFSTR or 
	                                     dfstr.confin) in the HOME directory
	                                     with a section [po2js] and a value 
	                                     'langs'.''' % ', ' .join(LANGS))

	parser_po2js.add_argument('src', 
	                          help='''The source directory, typically 
	                          core/translations.''')
	parser_po2js.add_argument('dest', help='The destination directory.')
	parser_po2js.add_argument('ref', 
	                          nargs='?',
	                          type=argparse.FileType('rb', 0),
	                          help='''Optional path to a .js file to check the
	                          completeness of the strings.''')
	parser_po2js.set_defaults(func=command_po2js)

	# js2db
	parser_db2js = subparsers.add_parser('db2js', 
	                                     help='''Create an .js file from an 
	                                     .db file.''')
	parser_db2js.add_argument('src',
	                          type=argparse.FileType('rb', 0),
	                          help='''The source file, typically
	                          english.db file.''')
	parser_db2js.add_argument('dest',
	                          type=argparse.FileType('wb', 0),
	                          help='src help')

	parser_db2js.set_defaults(func=command_db2js)


	for module in [js2db, verifyids, showconfig]:
		if hasattr(module, "setup_subparser"):
			getattr(module, "setup_subparser")(subparsers, config)


	args = parser.parse_args()
	args.func(args)

if __name__ == '__main__':
	main()