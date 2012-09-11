import os
import sys
import shutil
import time
import protoparser
import protoobjects
import utils
import minirest

INDENT = "  "



def indent(count): return count * INDENT

class GetID(object):
    def __init__(self, tmpl):
        self._count = 0
        self._tmpl = tmpl

    def get_id(self):
        self._count += 1
        return self._tmpl % self._count

_get_line_id = GetID("code-line-%s").get_id

SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))
CSS_CLASSES = {protoobjects.NUMBER: "number",
               protoobjects.BUFFER: "string",
               protoobjects.BOOLEAN: "boolean"}

RESOURCES = "doc_resources"
HEAD_INDEX = """<!doctype html>
<title>Scope Interface</title>
<link rel="stylesheet" href="./style/style.css">
<script src="./script/script.js"></script>
<h1>Scope Interface</h1>
"""
HEAD = """<!doctype html>
<title>%s.%s</title>
<link rel="stylesheet" href="./style/style.css">
<script src="./script/script.js"></script>
"""
H1 = """<h1>%s<span class="service-version">%s</spnan></h1>\n"""
H2 = """<h2 id="%s"><a href="#%s">%s</a></h2>\n"""
SIDEPANEL = """<div class="sidepanel">
<h3>Commands</h3>
<ul class="commands">
%s
</ul>
<h3>Events</h3>
<ul class="events">
%s
</ul>
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

class Service(object):
    def __init__(self, global_scope, protopath, dest):
        service = global_scope.service
        self.service = service
        version = map(int, service.version.split("."))
        if len(version) == 2: version.append(0)
        self.sort_key = 1e8 * version[0] + 1e4 * version[1] + version[2]
        self.service_version = version
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

def print_enum(fp, enum):
    fp.write("<div class=\"enum\">\n")
    fp.write("<pre class=\"code-line\">{</pre>\n")
    fp.write("<ul>")
    for field in enum.fields:
        fp.write("<li class=\"field\">\n")
        line_id = _get_line_id()
        fp.write(ENUM % (line_id, line_id, field.name, field.key))
        print_doc(fp, field)
        fp.write("</li>\n")
    fp.write("</ul>\n")
    fp.write("<pre class=\"code-line\">}</pre>\n")
    fp.write("</div>")

def print_message(fp, msg, depth=0, recurse_list=[]):
    fp.write("<div class=\"message\">\n")
    fp.write("<pre class=\"code-line\">{</pre>\n")
    fp.write("<ul>")
    for field in msg.fields:
        line_id = _get_line_id()
        fp.write("<li class=\"field\">\n")
        f_type = field.type
        css_class = CSS_CLASSES[f_type.sup_type] if f_type.sup_type in CSS_CLASSES else ""
        default_val = " [default = %s]" % field.default_value if field.default_value else ""
        args = line_id, line_id, field.q, css_class, field.full_type_name, field.name, field.key, default_val
        fp.write(FIELD % args)
        print_doc(fp, field, depth)
        if f_type.sup_type == protoobjects.MESSAGE:
            if not f_type in recurse_list:
                print_message(fp, f_type, depth, recurse_list[:] + [field.type])
        if f_type.sup_type == protoobjects.ENUM:
            print_enum(fp, f_type)
        fp.write("</li>\n")

    fp.write("</ul>\n")
    fp.write("<pre class=\"code-line\">}</pre>\n")
    fp.write("</div>")

def print_command(fp, command):
    fp.write(H2 % (command.name, command.name, command.name))
    line_id = _get_line_id()
    fp.write(COMMAND % (line_id, line_id, command.name, command.request_arg.name))
    print_message(fp, command.request_arg)
    line_id = _get_line_id()
    fp.write(RETURNS % (line_id, line_id, command.response_arg.name))
    print_message(fp, command.response_arg)
    line_id = _get_line_id()
    fp.write(KEY % (line_id, line_id, command.key))

def print_event(fp, event):
    fp.write(H2 % (event.name, event.name, event.name))
    line_id = _get_line_id()
    fp.write(EVENT % (line_id, line_id, event.name, event.response_arg.name))
    print_message(fp, event.response_arg)
    line_id = _get_line_id()
    fp.write(KEY % (line_id, line_id, event.key))

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

def print_index(fp, services_dict):
    fp.write(HEAD_INDEX)
    services = services_dict.items()
    services.sort(key= lambda s: s[0])
    fp.write("<div id=\"logo\"></div>\n")
    fp.write("<div class=\"index-view\">\n")
    for name, versions_dict in services:

        versions = versions_dict.items()
        versions.sort(key=lambda s: s[1].service_version[2], reverse=True)
        versions.sort(key=lambda s: s[1].service_version[1], reverse=True)
        versions.sort(key=lambda s: s[1].service_version[0], reverse=True)
        service = versions.pop(0)[1]
        fp.write("<h2><a href=\"%s\">%s <span class=\"service-version\">%s</span></a></h2>" % (service.file_name, name, service.service.version))
        #fp.write("<ul class=\"versions\">")
        #for version, service in versions:
        #    fp.write("<li>%s</li>" % version)
        #fp.write("</ul>")
    fp.write("</div>\n")




def get_scope_services(proto_paths, dest):
    services = {}
    for path in proto_paths:
        with open(path, "rb") as fp:
            g_scope = protoparser.parse(fp.read())
            service = services.setdefault(g_scope.service.name, {})
            service[g_scope.service.version] = Service(g_scope, path, dest)
    return services

def scope_doc(args):
    if not os.path.exists(args.dest): os.mkdir(args.dest)
    proto_paths = [args.src] if os.path.isfile(args.src) else utils.get_proto_files(args.src)
    services = get_scope_services(proto_paths, args.dest)
    with open(os.path.join(args.dest, "index.html"), "wb") as fp:
         print_index(fp, services)
    for service in services.values():
        for version in service.values():
            with open(version.html_path, "wb") as fp:
                print_service(fp, services, version.service)
    copy_html_src(os.path.join(SOURCE_ROOT, RESOURCES), args.dest)


def setup_subparser(subparsers, config):
    subp = subparsers.add_parser("scope-doc", help="Create scope interface documentation.")
    subp.add_argument("src", nargs="?", default=".", help="""proto file or directory (default: %(default)s)).""")
    subp.add_argument("dest", nargs="?",  default="msg-defs", help="the destination directory (default: %(default)s)).")
    subp.set_defaults(func=scope_doc)
