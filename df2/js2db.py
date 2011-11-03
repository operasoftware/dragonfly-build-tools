import os
import sys
import re
import codecs
import time
import argparse

def get_timestamp():
    return time.strftime("%a %d %b %Y %H:%M", time.localtime())

class JSFileParseError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

def js2db(args):
	RE_STR = re.compile(r"".join([
	         r"/\*\s*DESC:\s*((?:[^\*]|\*(?!/))*)\*/",
	         r"\s*ui_strings\.([^ =]*)\s*=",
	         r"\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')\s*;?\s*",
	         ]))

	out = []
	content = args.src.read()
	prev_match = None
	CAPTION = 3
	IDENTIFIER = 2
	DESCRIPTION = 1
	for match in RE_STR.finditer(content):
		ident = match.group(IDENTIFIER)
		caption = match.group(CAPTION).replace(""", """).replace("\\"", """)
		out.append("%s=-1" % ident)
		out.append("%s.caption=%s" % (ident, caption))
		out.append("%s.scope=\"dragonfly\"" % ident)
		out.append("%s.description=\"%s\"" % (ident, match.group(DESCRIPTION)))
		if prev_match:
			if match.start(0) - prev_match.end(0) > 1:
				raise JSFileParseError(content[prev_match.end(0):match.start(0)])
		prev_match = match

	args.dest.write("\n".join(out))

def setup_subparser(subparsers, config):
	subp = subparsers.add_parser("js2db", help="Create an .db file from an .js file.")
	subp.add_argument("src", type=argparse.FileType("rb", 0),
	                         help="""The source file, typically 
	                                 src/ui-strings/ui_strings-en.js.""")
	subp.add_argument("dest", type=argparse.FileType("wb", 0),
	                          help="the destination file.")
	subp.set_defaults(func=js2db)
