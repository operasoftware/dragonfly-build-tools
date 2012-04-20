import os
import sys
import re
import codecs
import time
import argparse

def get_timestamp():
    return time.strftime("%a %d %b %Y %H:%M", time.localtime())

"""
msgid "<LanguageCode>"
msgstr "en-GB"

#. Disable all event breakpoints
#. Scope: dragonfly
#: S_BUTTON_REMOVE_ALL_BREAKPOINTS:1313823321
#| msgctxt "S_BUTTON_REMOVE_ALL_BREAKPOINTS"
#| msgid "Remove all event breakpoints"



#. Scope: momail
#: S_LITERAL_CANCEL:972784745
#, python-format
msgctxt "S_LITERAL_CANCEL"
msgid ""
"Opera Dragonfly is waiting for a connection on port %s.\n"
"Please enter opera:debug in your device's URL field to connect."
msgstr "Abbrechen"
"""

class StringEscapeError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

class StringPlaceholderError(Exception):
	def __init__(self, path, value):
		self.value = path + "\n" + value
	def __str__(self):
		return self.value

class LanguageError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

class MissingIDError(Exception):
	def __init__(self, id_list, lang_file):
		self.value = "Missing ids: %s in %s" % (", ".join(id_list), lang_file)
	def __str__(self):
		return self.value

"""
#. Language name in its own language
msgid "<LanguageName>"
msgstr "Deutsch"

#. Two letter language code
msgid "<LanguageCode>"
msgstr "de"
"""

RE_LANG_NAME = re.compile(r"msgid \"<LanguageName>\"\s*msgstr (\"[^\"]*\")\s*")
RE_LANG_CODE = re.compile(r"msgid \"<LanguageCode>\"\s*msgstr (\"[^\"]*\")\s*")
RE_STR = re.compile(r"".join([
         r"(?:#\..*\s*)*",
         r"#:\s([^:]+):\d+\s*",
         r"(?:#, (?:c-format|fuzzy|python-format)\s*|#\|[^\r\n]*\s*)*",
         r"msgctxt\s*([^\r\n]*)\s*",
         r"msgid\s*((?:\"(?:.(?!\"[\r\n]))*.?\"\s+)+)",
         r"msgstr\s*((?:\"(?:.(?!\"[\r\n]))*.?\"\s+)+)",
         ]))
RE_SCOPE = re.compile(r"#\.\s*Scope:(?:.(?!dragonfly))*.dragonfly")
RE_PLACEHOLDERS = re.compile(r"(%(?:\([^\)]*\))?s)")
RE_LINEBREAK = re.compile(r"\"[\r\n]+\"")
RE_STR_CHECK = re.compile(r"(\"(?:[^\\\"]|\\.)*\")")
RE_ENG_JS_STR = re.compile(r"ui_strings\.([A-Z0-9_]+)")

LANG = 1
ID = 1
MSGID = 3
MSGSTR = 4

class JSWriter(object):
	def __init__(self, id_list=[]):
		self._out = []

	def write_head(self, name, match_name, match_code, source):
		lang = match_code.group(LANG)
		self._out.extend(["/* Generated from %s at %s */" % (name, get_timestamp()),
		                  "window.ui_strings || (window.ui_strings  = {});",
		                  "window.ui_strings.lang_code = %s;" % lang])
	
	def write_entry(self, match, msg_str):
		self._out.append("ui_strings.%s=%s;" % (match.group(ID), msg_str))

	def get_content(self):
		return "\n".join(self._out)

class PoWriter(object):
	def __init__(self, id_list=[]):
		self._out = []
		self._id_list = id_list

	def write_head(self, name, match_name, match_code, source):
		self._out.append(source[0:max(match_name.end(0), match_code.end(0))])
	
	def write_entry(self, match, msg_str):
		if match.group(ID) in self._id_list:
			self._out.append(match.group(0))

	def get_content(self):
		return "".join(self._out)

def get_ids_from_js(js_file):
	return [match.group(ID) for match in RE_ENG_JS_STR.finditer(js_file.read())]

def check_placeholders(src_str, dest_str):
	dest_placeh = RE_PLACEHOLDERS.findall(dest_str)
	return all([m in dest_placeh for m in RE_PLACEHOLDERS.findall(src_str)])

def po2(in_file, name, writer):
	ids = []
	with open(in_file, "rb") as f:
		content = f.read()
		match_code = RE_LANG_CODE.search(content)
		match_name = RE_LANG_NAME.search(content)
		if not (match_code and match_name):
			raise LanguageError(in_file)
		writer.write_head(name, match_name, match_code, content)
		for match in RE_STR.finditer(content):
			if RE_SCOPE.search(match.group(0)):
				msg_id = RE_LINEBREAK.sub("", match.group(MSGID).strip())
				msg_str = RE_LINEBREAK.sub("", match.group(MSGSTR).strip())
				if RE_STR_CHECK.sub("", msg_str):
					raise StringEscapeError(match.group(0))
				if not check_placeholders(msg_id, msg_str):
					raise StringPlaceholderError(in_file, match.group(0))
				writer.write_entry(match, msg_str)
				ids.append(match.group(ID))

	return ids

def command_po2(args, writer_class, f_name_tmpl, id_list=None):
	src, dest = args.src, args.dest
	ref_ids = []
	if hasattr(args, "ref") and args.ref:
		ref_ids = set(get_ids_from_js(args.ref))
	if not os.path.exists(dest): 
		os.makedirs(dest)

	langs = args.config.get("po2js", {}).get("langs", [])

	for root, dirs, files in os.walk(src):
		absroot = os.path.abspath(root)
		if "unite" in absroot:
			continue
		for name in files:
			if name.endswith(".po"):
				lang = name[:-3]
				if lang in langs:
					root = os.path.normpath(root)
					writer = writer_class(id_list)
					ids = po2(os.path.join(root, name), name, writer)
					js_file = f_name_tmpl % name[:-3]
					if ref_ids and not ref_ids == set(ids):
						ids = set(ids)
						diff = ref_ids - ids
						if diff:
							print "Error: Missing ids in %s\n" % name
							for i in sorted(list(diff)):
								if i:
									print "\t", i
							print ""
						diff = ids - ref_ids
						if diff:
							print "Warning: Missing ids in %s\n" % args.ref.name
							for i in sorted(list(diff)):
								if i:
									print "\t", i
							print ""
					with open(os.path.join(dest, js_file), "wb") as f:
						f.write(codecs.BOM_UTF8)
						f.write(writer.get_content())
						print "written %s." % js_file

def command_po2js(args):
	command_po2(args, JSWriter, "ui_strings-%s.js")

def command_po2po(args):
	args.id_list = list(set(get_ids_from_js(args.ref)))
	command_po2(args, PoWriter, "%s.po", args.id_list)
						
def setup_subparser(subparsers, config):
	subp = subparsers.add_parser("po2js", help="Covert .po files to .js files.")
	subp.add_argument("src", 
	                  help="The source directory, typically core/translations.")
	subp.add_argument("dest", help="The destination directory.")
	subp.add_argument("ref", 
	                  nargs="?",
	                  type=argparse.FileType("rb", 0),
	                  help="""Optional path to a .js file to check the
	                          completeness of the strings.""")
	subp.set_defaults(func=command_po2js)


	subp = subparsers.add_parser("po2po", help="Filter po files by a set of IDs.")
	subp.add_argument("src", 
	                  help="The source directory, typically core/translations.")
	subp.add_argument("dest", help="The destination directory.")
	subp.add_argument("ref", 
	                  type=argparse.FileType("rb", 0),
	                  help="""Path to a file to extract string ids.
	                          The script searchs with the pattern 
	                          "ui_strings\.([A-Z0-9_]+)" """)
	subp.set_defaults(func=command_po2po)
