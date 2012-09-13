import os
import sys
import shutil
import time
import protoparser
import protoobjects
import utils
import minirest

def get_timestamp(): return time.strftime("%A, %d %b %Y %H:%M", time.localtime())

INDENT = "  "
def indent(count): return count * INDENT

def get_field_id(cmd_or_ev_name, recurse_list, field=""):
    if field:
        return "%s.%s.%s" % (cmd_or_ev_name, ".".join((m.name for m in recurse_list)), field.name)
    return "%s.%s" % (cmd_or_ev_name, ".".join((m.name for m in recurse_list)))

SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))
CSS_CLASSES = {protoobjects.NUMBER: "number",
               protoobjects.BUFFER: "string",
               protoobjects.BOOLEAN: "boolean"}
RESOURCES = "doc_resources"
# index page
HEAD_INDEX = """<!doctype html>
<title>Scope Interface</title>
<link rel="stylesheet" href="./style/style.css">
<script src="./script/script.js"></script>
<h1>Scope Interface <span class="service-version">STP/1</span></h1>
"""
SIDEPANEL_INDEX = """<div class="sidepanel">
<h3>All versions</h3>
<ul class=\"all-service-versions\">
%s
</ul>
<div id="logo"><p class="last-created">%s</p></div>
</div>
"""
MAIN_INDEX = """<div class="index-view">
%s
<h2 class="all-versions">All versions</h2>
%s
</div>
"""
H2_INDEX = """<h2><a href="%s">%s <span class="service-version">%s</span></a></h2>"""
H3_INDEX = """<li><h3 id="%s"><a href="%s">%s <span class="service-version">%s</span></a></h3></li>"""
H3_INDEX_ONLY_VERSION = """<h3><a href="%s">&nbsp;<span class="service-version">%s</span></a></h3>"""
# service interface
HEAD = """<!doctype html>
<title>%s.%s</title>
<link rel="stylesheet" href="./style/style.css">
<script src="./script/script.js"></script>
"""
H1 = """<h1>%s<span class="service-version">%s</spnan></h1>\n"""
H2 = """<h2 id="%s"><a href="#%s">%s</a></h2>\n"""
SIDEPANEL = """<div class="sidepanel">
<p class="back"><a href="./index.html">back</a></p>
<h3>Commands</h3>
<ul class="commands">
%s
</ul>
<h3>Events</h3>
<ul class="events">
%s
</ul>
<div title="Hint: hold shift to unfold all sub messages" class="setting">
 <label><input type="checkbox" class="default-collapse"> collapse all by default</label>
 </div>
</div>
"""
SIDEPANLE_LINK = """<li><a href="#%s">%s</a></li>\n"""
COMMAND = "".join(("<pre class=\"code-line\" id=\"%s\">",
                   "<a href=\"#%s\">",
                   "<span class=\"keyword\">command</span>",
                   " <span class=\"command-name\">%s</span>",
                   "(<span class=\"message-name\">%s</span>)",
                   "</a>",
                   "</pre>"))
RETURNS = "".join(("<pre class=\"code-line\" id=\"%s\">",
                   "<a href=\"#%s\">",
                   "<span class=\"keyword\">returns</span>",
                   " (<span class=\"message-name\">%s</span>)",
                   "</a>",
                   "</pre>"))
KEY = "".join(("<pre class=\"code-line\" id=\"%s\">",
               "<a href=\"#%s\">",
               "<span class=\"proto-key\">= %s;</span>",
               "</a>",
               "</pre>"))
EVENT = "".join(("<pre class=\"code-line\" id=\"%s\">",
                 "<a href=\"#%s\">",
                 "<span class=\"keyword\">event</span>",
                 " <span class=\"command-name\">%s</span>",
                 "<span class=\"keyword\"> returns </span>",
                 "(<span class=\"message-name\">%s</span>)",
                 "</a>",
                 "</pre>"))
FIELD = "".join(("<pre class=\"code-line\" id=\"%s\">",
                 "%s",
                 "<a href=\"#%s\">",
                 "<span class=\"qualifier\">%s</span>",
                 " <span class=\"%s\">%s</span>",
                 " <span class=\"field-name\">%s</span>",
                 "<span class=\"proto-key\"> = %s</span>",
                 "%s",
                 "<span class=\"proto-key\">;</span>",
                 "</a>",
                 "</pre>"))
ENUM = "".join(("<pre class=\"code-line\" id=\"%s\">",
                "<a href=\"#%s\">",
                "<span class=\"enum-name\">%s</span>",
                "<span class=\"proto-key\"> = </span>",
                "<span class=\"enum-key\">%s</span>",
                "<span class=\"proto-key\">;</span>",
                "</a>",
                "</pre>"))
EXPANDER = """<span class="expander">&nbsp;</span>"""

class ServiceDoc(object):
    def __init__(self, global_scope, protopath, dest):
        service = global_scope.service
        self.service = service
        self.protopath = protopath
        self.file_name = "%s.%s.html" % (service.name, service.version)
        self.html_path = os.path.join(dest, self.file_name)
        self.global_scope = global_scope

def copy_html_src(html_src, dest):
    for d in ["style", "script"]:
        dest_path = os.path.join(dest, d)
        if os.path.exists(dest_path): shutil.rmtree(dest_path)
        shutil.copytree(os.path.join(html_src, d), dest_path)

def print_doc(fp, obj, depth=0):
    if obj.doc:
        fp.write("<div class=\"doc\">")
        fp.write(minirest.process(obj.doc_lines).serialize())
        fp.write("</div>")

def print_enum(fp, cmd_or_ev_name, enum, recurse_list):
    fp.write("<div class=\"enum\">\n")
    fp.write("<pre class=\"code-line\">{</pre>\n")
    fp.write("<ul>")
    if enum.doc:
        fp.write("<li class=\"message-doc\">\n")
        print_doc(fp, enum)
        fp.write("</li>\n")
    for field in enum.fields:
        fp.write("<li class=\"field\">\n")
        field_id = get_field_id(cmd_or_ev_name, recurse_list, field)
        fp.write(ENUM % (field_id, field_id, field.name, field.key))
        print_doc(fp, field)
        fp.write("</li>\n")
    fp.write("</ul>\n")
    fp.write("<pre class=\"code-line\">}</pre>\n")
    fp.write("</div>")

def print_message(fp, cmd_or_ev_name, msg, depth=0, recurse_list=[]):
    fp.write("<div class=\"message\">\n")
    fp.write("<pre class=\"code-line\">{</pre>\n")
    fp.write("<ul>")
    if msg.doc:
        fp.write("<li class=\"message-doc\">\n")
        print_doc(fp, msg, depth)
        fp.write("</li>\n")
    for field in msg.fields:
        field_id = get_field_id(cmd_or_ev_name, recurse_list, field)
        fp.write("<li class=\"field\">\n")
        f_type = field.type
        has_expander = (f_type.is_message and not f_type in recurse_list) or f_type.is_enum
        expander = EXPANDER if has_expander else ""
        css_class = CSS_CLASSES[f_type.sup_type] if f_type.sup_type in CSS_CLASSES else ""
        default_val = " [default = %s]" % field.default_value if field.default_value else ""
        args = field_id, expander, field_id, field.q, css_class, field.full_type_name, field.name, field.key, default_val
        fp.write(FIELD % args)
        print_doc(fp, field, depth)
        if f_type.is_message and not f_type in recurse_list:
            print_message(fp, cmd_or_ev_name, f_type, depth, recurse_list[:] + [field.type])
        if f_type.is_enum:
            print_enum(fp, cmd_or_ev_name, f_type, recurse_list)
        fp.write("</li>\n")
    fp.write("</ul>\n")
    fp.write("<pre class=\"code-line\">}</pre>\n")
    fp.write("</div>")

def print_command(fp, command):
    fp.write(H2 % (command.name, command.name, command.name))
    if command.doc: print_doc(fp, command)
    recurse_list = [command.request_arg]
    field_id = get_field_id(command.name, recurse_list)
    fp.write(COMMAND % (field_id, field_id, command.name, command.request_arg.name))
    print_message(fp, command.name, command.request_arg, recurse_list=recurse_list)
    recurse_list = [command.response_arg]
    field_id = get_field_id(command.name, recurse_list)
    fp.write(RETURNS % (field_id, field_id, command.response_arg.name))
    print_message(fp, command.name, command.response_arg, recurse_list=recurse_list)
    field_id = "%s.key" % command.name
    fp.write(KEY % (field_id, field_id, command.key))

def print_event(fp, event):
    fp.write(H2 % (event.name, event.name, event.name))
    if event.doc: print_doc(fp, event)
    recurse_list = [event.response_arg]
    field_id = get_field_id(event.name, recurse_list)
    fp.write(EVENT % (field_id, field_id, event.name, event.response_arg.name))
    print_message(fp, event.name, event.response_arg, recurse_list=recurse_list)
    field_id = "%s.key" % event.name
    fp.write(KEY % (field_id, field_id, event.key))

def print_service(fp, services, service):
    fp.write(HEAD % (service.name, service.version))
    fp.write(H1 % (service.name, service.version))
    cmds = service.command_names
    evs = service.event_names
    fp.write(SIDEPANEL % ("\n".join((SIDEPANLE_LINK % (cmd, cmd) for cmd in cmds)),
                          "\n".join((SIDEPANLE_LINK % (ev, ev) for ev in evs))))
    fp.write("<div class=\"main-view\">\n")
    if service.doc: print_doc(fp, service)
    for cmd in cmds: print_command(fp, getattr(service, cmd))
    for ev in evs: print_event(fp, getattr(service, ev))
    fp.write("</div>\n")

def print_index(fp, services_dict, dest):
    fp.write(HEAD_INDEX)
    services = services_dict.items()
    services.sort(key= lambda s: s[0])
    all_versions_list = []
    latest_versions = []
    all_versions = []
    for name, versions_dict in services:
        all_versions_list.append(SIDEPANLE_LINK % (name, name))
        versions = versions_dict.values()
        versions.sort(key=lambda s: s.service.patch_version, reverse=True)
        versions.sort(key=lambda s: s.service.minor_version, reverse=True)
        versions.sort(key=lambda s: s.service.major_version, reverse=True)
        latest = versions[0]
        latest_file_name = "%s.html" % name
        latest_versions.append(H2_INDEX  % (latest_file_name, name, latest.service.version))
        shutil.copyfile(os.path.join(dest, latest.file_name), os.path.join(dest, latest_file_name))
        all_versions.append("<ul class=\"all-version-list\">\n")
        for version in versions:
            if version == latest:
                args = name, version.file_name, name, version.service.version
                all_versions.append(H3_INDEX % args)
            else:
                args = version.file_name, version.service.version
                all_versions.append(H3_INDEX_ONLY_VERSION % args)
        all_versions.append("</ul>\n")
    fp.write(SIDEPANEL_INDEX % ("".join(all_versions_list), get_timestamp()))
    fp.write(MAIN_INDEX % ("".join(latest_versions), "".join(all_versions)))

def get_scope_services(proto_paths, dest):
    services = {}
    for path in proto_paths:
        with open(path, "rb") as fp:
            g_scope = protoparser.parse(fp.read())
            service = services.setdefault(g_scope.service.name, {})
            service[g_scope.service.version] = ServiceDoc(g_scope, path, dest)
    return services

def scope_doc(args):
    if not os.path.exists(args.dest): os.mkdir(args.dest)
    proto_paths = [args.src] if os.path.isfile(args.src) else utils.get_proto_files(args.src)
    services = get_scope_services(proto_paths, args.dest)
    for service in services.values():
        for version in service.values():
            with open(version.html_path, "wb") as fp:
                print_service(fp, services, version.service)
    with open(os.path.join(args.dest, "index.html"), "wb") as fp:
         print_index(fp, services, args.dest)
    copy_html_src(os.path.join(SOURCE_ROOT, RESOURCES), args.dest)

def setup_subparser(subparsers, config):
    subp = subparsers.add_parser("scope-doc", help="Create scope interface documentation.")
    subp.add_argument("src", nargs="?", default=".", help="""proto file or directory (default: %(default)s)).""")
    subp.add_argument("dest", nargs="?",  default="msg-defs", help="the destination directory (default: %(default)s)).")
    subp.set_defaults(func=scope_doc)
