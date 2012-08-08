import os
import sys
import re
import codecs
import time
import argparse
import db2js
import codecs

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
	IDENTIFIER = 2
	for match in RE_STR.finditer(content):
		ident = match.group(IDENTIFIER)
		out.append((match.group(IDENTIFIER), match.group(0).strip()))
		if prev_match:
			if match.start(0) - prev_match.end(0) > 1:
				raise JSFileParseError(content[prev_match.end(0):match.start(0)])
		prev_match = match
	ID = 0
	ENTRY = 1
	out_sorted = sorted(out, key=lambda item: item[ID])
	previous = None
	duplicates = []
	for ident, entry in out_sorted:
		if previous and ident == previous[ID]:
			print "duplicated ID: %s" % ident
			if entry == previous[ENTRY]:
				duplicates.append((ident, entry))
		previous = (ident, entry)
	for item in duplicates:
		out_sorted.pop(out_sorted.index(item))
		print "removed duplicated entry in ui strings\n %s" % item[ENTRY]
	with open(args.src, "wb") as f:
		f.write(codecs.BOM_UTF8)
		f.write(db2js.HEAD)
		for e in out_sorted:
			f.write(e[1])
			f.write("\n\n")

def setup_subparser(subparsers, config):
	subp = subparsers.add_parser("jssort", help="Sort the entries in a .js file by the IDs in place.")
	subp.add_argument("src", help="""The source file, typically
	                                 src/ui-strings/ui_strings-en.js.""")
	subp.set_defaults(func=jssort)
