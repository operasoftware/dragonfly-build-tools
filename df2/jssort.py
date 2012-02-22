import os
import sys
import re
import codecs
import time
import argparse
import db2js

def get_timestamp():
    return time.strftime("%a %d %b %Y %H:%M", time.localtime())

class JSFileParseError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

class MissingSRC(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

def jssort(args):
	RE_STR = re.compile(r"".join([
	         r"/\*\s*DESC:\s*((?:[^\*]|\*(?!/))*)\*/",
	         r"\s*ui_strings\.([^ =]*)\s*=",
	         r"\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')\s*;?\s*",
	         ]))


	out = []
	content = None
	with open(args.src, "rb") as f:
		content = f.read()
		f.close()
	if not content:
		raise MissingSRC(args.src)
	prev_match = None
	CAPTION = 3
	IDENTIFIER = 2
	DESCRIPTION = 1
	for match in RE_STR.finditer(content):
		ident = match.group(IDENTIFIER)
		out.append((match.group(IDENTIFIER), match.group(0)))
		if prev_match:
			if match.start(0) - prev_match.end(0) > 1:
				raise JSFileParseError(content[prev_match.end(0):match.start(0)])
		prev_match = match

	out_sorted = sorted(out, key=lambda item: item[0])
	with open(args.src, "wb") as f:
		f.write(db2js.HEAD)
		for e in out_sorted:
			f.write(e[1])

def setup_subparser(subparsers, config):
	subp = subparsers.add_parser("jssort", help="Sort the entries in a .js file by the IDs in place.")
	subp.add_argument("src", help="""The source file, typically 
	                                 src/ui-strings/ui_strings-en.js.""")
	subp.set_defaults(func=jssort)
