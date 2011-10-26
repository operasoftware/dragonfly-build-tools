import os
import sys
import re
import codecs
import time

def get_timestamp():
    return time.strftime("%a %d %b %Y %H:%M", time.localtime())

LANGS = ['be', 'bg', 'cs', 'da', 'de', 'el', 'en-GB', 'es-ES', 'es-LA', 'et', 
         'fi', 'fr', 'fr-CA', 'fy', 'gd', 'hi', 'hr', 'hu', 'id', 'it', 'ja', 
         'ka', 'ko', 'lt', 'mk', 'nb', 'nl', 'nn', 'pl', 'pt', 'pt-BR', 'ro', 
         'ru', 'sk', 'sr', 'sv', 'ta', 'te', 'tr', 'uk', 'vi', 'zh-cn', 'zh-tw']

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
		self.value = path + '\n' + value
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

RE_LANG = re.compile(r"msgid \"<LanguageCode>\"\s*msgstr (\"[^\"]*\")")

RE_STR = re.compile(r"".join([
         r"#\.\s*Scope:(?:.(?!dragonfly))*.dragonfly[^\r\n]*\s*",
         r"#:\s([^:]+):\d+\s*",
         r"(?:#, (?:c-format|fuzzy)\s*|#\|[^\r\n]*\s*)*",
         r"msgctxt\s*([^\r\n]*)\s*",
         r"msgid\s*((?:\"(?:.(?!\"[\r\n]))*.?\"\s+)+)",
         r"msgstr\s*((?:\"(?:.(?!\"[\r\n]))*.?\"\s+)+)",
         ]))


RE_PLACEHOLDERS = re.compile(r"(%(?:\([^\)]*\))?s)")
RE_LINEBREAK = re.compile(r"\"[\r\n]+\"")
RE_STR_CHECK = re.compile(r"(\"(?:[^\\\"]|\\.)*\")")
LANGS = ['be', 'bg', 'cs', 'da', 'de', 'el', 'en-GB', 'es-ES', 'es-LA', 'et', 
         'fi', 'fr', 'fr-CA', 'fy', 'gd', 'hi', 'hr', 'hu', 'id', 'it', 'ja', 
         'ka', 'ko', 'lt', 'mk', 'nb', 'nl', 'nn', 'pl', 'pt', 'pt-BR', 'ro', 
         'ru', 'sk', 'sr', 'sv', 'ta', 'te', 'tr', 'uk', 'vi', 'zh-cn', 'zh-tw']

def get_ids_from_js(js_file):
	ID = 1
	# RE_ENG_JS_STR = re.compile(r"ui_strings\.([A-Z0-9_]*)\s*=")
	RE_ENG_JS_STR = re.compile(r"ui_strings\.([A-Z0-9_]*)")
	return [match.group(ID) for match in RE_ENG_JS_STR.finditer(js_file.read())]

def check_placeholders(src_str, dest_str):
	dest_placeh = RE_PLACEHOLDERS.findall(dest_str)
	return all([m in dest_placeh for m in RE_PLACEHOLDERS.findall(src_str)])

def po2js(in_file, name):

	LANG = 1
	SCOPE = 1
	ID = 1
	MSGCTXT = 2
	MSGID = 3
	MSGSTR = 4
	STR_CHECK = 5
	
	with open(in_file, "rb") as f:
		content = f.read()
		match = RE_LANG.search(content)
		if not match:
			raise LanguageError(match.group(0))
		lang = match.group(LANG)
		out = ["/* Generated from %s at %s */" % (name, get_timestamp()),
		       "window.ui_strings || (window.ui_strings  = {});",
		       "window.ui_strings.lang_code = %s;" % lang]
		ids = []
		for match in RE_STR.finditer(content):
			msg_id = RE_LINEBREAK.sub("", match.group(MSGID).strip())
			msg_str = RE_LINEBREAK.sub("", match.group(MSGSTR).strip())
			if RE_STR_CHECK.sub("", msg_str):
				raise StringEscapeError(match.group(0))
			if not check_placeholders(msg_id, msg_str):
				raise StringPlaceholderError(in_file, match.group(0))
			out.append("ui_strings.%s=%s;" % (match.group(ID), msg_str))
			ids.append(match.group(ID))

	return out, ids

def command_po2js(args):
	src, dest, ref = args.src, args.dest, args.ref
	ref_ids = []
	if args.ref:
		ref_ids = set(get_ids_from_js(ref))
	if not os.path.exists(dest): 
		os.makedirs(dest)

	for root, dirs, files in os.walk(src):
		absroot = os.path.abspath(root)
		if "unite" in absroot:
			continue
		for name in files:
			if name.endswith(".po"):
				lang = name[:-3]
				if lang in LANGS:
					root = os.path.normpath(root)
					out, ids = po2js(os.path.join(root, name), name)
					js_file = "ui_strings-%s.js" % name[:-3]
					if ref_ids and not ref_ids == set(ids):
						ids = set(ids)
						diff = ref_ids - ids if ref_ids > ids else ids - ref_ids
						print "Error: Missing %s ids in %s" % (list(diff), name)
					with open(os.path.join(dest, js_file), "wb") as f:
						f.write(codecs.BOM_UTF8)
						f.write("\n".join(out)) 
