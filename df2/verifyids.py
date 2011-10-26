import argparse
import os
from po2js import get_ids_from_js

class ExcludDirsAction(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		setattr(namespace, self.dest, [os.path.normpath(p) for p in values])

def verifyids(args):
	src_ids = set(get_ids_from_js(args.src))
	dest_ids = set()

	for root, dirs, files in os.walk(args.dest):
		n_root = os.path.normpath(root)
		if [p for p in args.exclude if n_root.endswith(p)]:
			while dirs:
				dirs.pop()
			continue
		
		for name in files:
			if name.endswith(".js"):
				with open(os.path.join(root, name), "rb") as f:
					dest_ids.update(get_ids_from_js(f))

	if src_ids > dest_ids:
		print "unused IDs %s" % list(src_ids - dest_ids)
	elif src_ids < dest_ids:
		print "missing IDs: %s" % list(dest_ids - src_ids)
	else:
		print "everything is ok, total %s IDs" % len(src_ids)


def setup_subparser(subparsers, config):
	subp = subparsers.add_parser('verifyids',
	                             help='''Verify that all IDs in src are used 
	                                     in dest and all IDs used in dest are 
	                                     defined in src.''')
	subp.add_argument('src',
	                  type=argparse.FileType('rb', 0),
	                  help='''The refrence source file, typically
	                          ui_strings-en.js.''')
	subp.add_argument('dest',
	                  help='''The destination to verify the ids.''')
	subp.add_argument('-X', '--exclude',
	                  nargs='*',
	                  action=ExcludDirsAction,
	                  default=[],
	                  help='Directories to be excluded from the destination.')
	subp.set_defaults(func=verifyids)

