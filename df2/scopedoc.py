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

SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))
CSS_CLASSES = {protoobjects.NUMBER: "number",
               protoobjects.BUFFER: "string",
               protoobjects.BOOLEAN: "boolean"}

RESOURCES = "doc_resources"

HEAD = """<!doctype html>
<title>%s.%s</title>
<link rel="stylesheet" href="%s">
"""

SIDEPANEL = """<div class="sidepanel">
<h3>command*</h3>
<ul class="commands">
%s
</ul>
<h3>event*</h3>
<ul class="events">
%s
</ul>
</div>
"""


COMMAND = "".join(("<pre class=\"command-declaration\">",
                   "<span class=\"keyword\">command</span>",
                   " <span class=\"command-name\">%s</span>",
                   "(<span class=\"message-name\">%s</span>)",
                   "</pre>"))
EVENT = "".join(("<pre class=\"command-declaration\">",
                   "<span class=\"keyword\">event</span>",
                   " <span class=\"command-name\">%s</span>",
                   "<span class=\"keyword\"> returns </span>",
                   "(<span class=\"message-name\">%s</span>)",
                   "</pre>"))
FIELD = "".join(("<pre class=\"field-description\">",
                 "<span class=\"qualifier\">%s</span>",
                 " <span class=\"%s\">%s</span>",
                 " <span class=\"field-name\">%s</span>",
                 " = ",
                 "<span class=\"proto-key\">%s</span>",
                 "%s;",
                 "</pre>"))

RETURNS = "".join(("<pre class=\"command-declaration\">",
                  "<span class=\"keyword\">returns</span>",
                  " (<span class=\"message-name\">%s</span>)",
                  "</pre>"))

KEY = "".join(("<pre class=\"command-declaration\">",
                 "= ",
                 "<span class=\"proto-key\">%s</span>;",
                 "</pre>"))


class Service(object):
    def __init__(self, global_scope, protopath, dest):
        service = global_scope.service
        self.service = service
        self.protopath = protopath
        self.html_path = os.path.join(dest, "%s.%s.html" % (service.name, service.version))
        self.global_scope = global_scope

def copy_html_src(html_src, dest):
    for d in ["style"]:
        dest_path = os.path.join(dest, d)
        if os.path.exists(dest_path): shutil.rmtree(dest_path)
        shutil.copytree(os.path.join(html_src, d), dest_path)

def print_doc(fp, obj, depth=0):
    if obj.doc:
        fp.write("<div class=\"doc\">")
        fp.write(minirest.process(obj.doc_lines).serialize())
        fp.write("</div>")



def print_message(fp, msg, depth=0, recurse_list=[]):
    fp.write("<div class=\"message\">")
    fp.write("<pre class=\"message-description\">{</pre>")
    fp.write("<ul>")
    for field in msg.fields:
        fp.write("<li class=\"field\">")
        f_type = field.type
        css_class = CSS_CLASSES[f_type.sup_type] if f_type.sup_type in CSS_CLASSES else ""
        default_val = " [default = %s]" % field.default_value if field.default_value else ""
        args = field.q, css_class, field.full_type_name, field.name, field.key, default_val
        fp.write(FIELD % args)
        print_doc(fp, field, depth)
        if f_type.sup_type == protoobjects.MESSAGE:
            if not f_type in recurse_list:
                print_message(fp, f_type, depth, recurse_list[:] + [field.type])
        # if field.type.sup_type == protoobjects.ENUM:
        #     print_enum(fp, field.type, depth)
        fp.write("</li>")

    fp.write("</ul>")
    fp.write("<pre class=\"message-description\">}</pre>")
    fp.write("</div>")

def print_command(fp, command):
    fp.write("<h2 id=\"%s\">%s</h2>" % (command.name, command.name))
    fp.write(COMMAND % (command.name, command.request_arg.name))
    print_message(fp, command.request_arg)
    fp.write(RETURNS % command.response_arg.name)
    print_message(fp, command.response_arg)
    fp.write(KEY % command.key)

def print_event(fp, event):
    fp.write("<h2 id=\"%s\">%s</h2>" % (event.name, event.name))
    fp.write(EVENT % (event.name, event.response_arg.name))
    print_message(fp, event.response_arg)
    fp.write(KEY % event.key)

def print_service(fp, services, service):
    fp.write(HEAD % (service.name, service.version, "./style/style.css"))
    fp.write("<h1>%s<span class=\"service-version\">%s</spnan></h1>" % (service.name, service.version))
    cmds = map(lambda c: c.name, service.commands)
    cmds.sort()
    evs = map(lambda e: e.name, service.events)
    evs.sort()
    fp.write(SIDEPANEL % ("\n".join(("<li><a href=\"#%s\">%s</a></li>" % (cmd, cmd) for cmd in cmds)),
                          "\n".join(("<li><a href=\"#%s\">%s</a></li>" % (ev, ev) for ev in evs))))

    fp.write("<div class=\"main-view\">")
    if service.doc:
        print_doc(fp, service)
    for cmd in cmds:
        print_command(fp, getattr(service, cmd))
    for ev in evs:
        print_event(fp, getattr(service, ev))
    fp.write("</div class=\"main-view\">")



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
