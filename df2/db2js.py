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

"""
S_LITERAL_AGREE=-1
S_LITERAL_AGREE.caption="Agree"
S_LITERAL_AGREE.description="String caption will never change. Used for Agree button or similar, where the user agrees to a proposed action."
S_LITERAL_AGREE.scope="bream"

C:\docs\git\strings\data\strings\english.db
"""

RE_ENG_DB_STR = re.compile(r"".join([
                r"(?P<ID>[A-Z0-9_]*)=-1\s*",
                r"(?:",
                r"\1\.caption=\"(?P<CAPTION>(?:.(?!\"[\r\n]))*.?)\"\s+|",
                r"\1\.description=(?P<DESC>\"(?:.(?!\"[\r\n]))*.?\")\s+|",
                r"\1\.scope=(?:.(?!dragonfly))*.dragonfly[^\r\n]*\s*",
                r"){3}"
                ]))

HEAD = """window.ui_strings || ( window.ui_strings  = {} );
window.ui_strings.lang_code = "en";

/**
 * Capitalization guidelines:
 * http://library.gnome.org/devel/hig-book/stable/design-text-labels.html.en#layout-capitalization
 *
 * Prefix -> use mapping for strings:
 * Prefix   Use
 * D        Dialog titles and components
 * S        General strings
 * M        Menus
 */

"""

ENTRY = """/* DESC: %s */
ui_strings.%s = "%s";
"""

RE_ESC_QUOTES = re.compile(r"(?<!\\)\"")

def db2js(args):

	out = []
	content = args.src.read()
	for match in RE_ENG_DB_STR.finditer(content):
		out.append((match.group("DESC").strip(" \""),
		            match.group("ID"),
		            RE_ESC_QUOTES.sub("\\\"", match.group("CAPTION"))))
	out.sort(key=lambda entry: entry[1])
	args.dest.write(HEAD)
	args.dest.write("\n".join([ENTRY % entry for entry in out]))

def setup_subparser(subparsers, config):
	subp = subparsers.add_parser("db2js", help="""Create an .js file from a .db file.""")
	subp.add_argument("src", type=argparse.FileType("rb", 0),
	                         help="""The source file, typically english.db file.""")
	subp.add_argument("dest", type=argparse.FileType("wb", 0), help="the destination file.")
	subp.set_defaults(func=db2js)
