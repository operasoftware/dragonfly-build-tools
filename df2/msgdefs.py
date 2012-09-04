import os
import sys
import time
import protoparser
import protoobjects
import utils

INDENT = "  "

CSS_CLASSES = {
    protoobjects.NUMBER: "number",
    protoobjects.BUFFER: "string",
    protoobjects.BOOLEAN: "boolean",
}

def indent(count): return count * INDENT

def print_doc(file, field, depth):
    if field.doc:
        file.write("%s%s" % (indent(depth), "<span class=\"comment\">/**\n"))
        for line in field.doc_lines:
            file.write("%s%s%s\n" % (indent(depth), "  * ", line.replace("&", "&amp;").replace("<", "&lt;")))
        file.write(indent(depth) + "  */</span>\n")

def print_enum(file, enum, depth=0):
    file.write("%s{\n" % indent(depth))
    depth += 1
    for f in enum.fields:
        print_doc(file, f, depth)
        args = indent(depth), f.name, f.key
        file.write("%s<span class=\"enum\">%s</span> = %s;\n" % args)
    depth -= 1
    file.write("%s}\n" % (indent(depth)))

def print_message(file, msg, include_message_name=True, depth=0, recurse_list=[]):
    if include_message_name:
        file.write("%smessage <span class=\"message\">%s</span>\n" % (indent(depth),  msg.name))
    file.write("%s{\n" % indent(depth))
    depth += 1
    for field in msg.fields:
        f_type = field.type
        print_doc(file, field, depth)
        if f_type.sup_type  in CSS_CLASSES:
            args = indent(depth), field.q, CSS_CLASSES[f_type.sup_type], field.full_type_name, field.name, field.key
            file.write("%s%s <span class=\"%s\">%s</span> %s = %s" % args)
        else:
            args = indent(depth), field.q, field.full_type_name, field.name, field.key
            file.write("%s%s %s %s = %s" % args)
        if hasattr(field.options, "default"):
            file.write(" [default = %s]" % field.options.default.value)
        file.write(";\n")
        if f_type.sup_type == protoobjects.MESSAGE:
            if not f_type in recurse_list:
                print_message(file, f_type, False, depth, recurse_list[:] + [field.type])
        if field.type.sup_type == protoobjects.ENUM:
            print_enum(file, field.type, depth)

    depth -= 1
    file.write("%s}\n" % (indent(depth)))

def print_msg_def(dest, service, type, command_or_event, message):
    service_name = service.name
    version = service.options.version.value.strip("\"")
    file_name = "%s.%s.%s.%s.def" % (service_name, version, type, command_or_event.name)
    with open(os.path.join(dest, file_name), "wb") as file:
        print_message(file, message)

def print_msg_defs(proto_path, dest):
    with open(proto_path, "rb") as proto_file:
        global_scope = protoparser.parse(proto_file.read())
        for c in global_scope.service.commands:
            print_msg_def(dest, global_scope.service, "commands", c, c.request_arg)
            print_msg_def(dest, global_scope.service, "responses", c, c.response_arg)
        for e in global_scope.service.events:
            print_msg_def(dest, global_scope.service, "events", e, e.response_arg)

def msg_defs(args):
    if not os.path.exists(args.dest): os.mkdir(args.dest)
    if os.path.isfile(args.src):
        print_masg_defs(args.src, args.dest)
    elif os.path.isdir(args.src):
        for path in utils.get_proto_files(args.src):
            print_msg_defs(path, args.dest)

def setup_subparser(subparsers, config):
    subp = subparsers.add_parser("msg-defs", help="Create html documentation.")
    subp.add_argument("src", nargs="?", default=".", help="""proto file or directory (default: %(default)s)).""")
    subp.add_argument("dest", nargs="?",  default="msg-defs", help="the destination directory (default: %(default)s)).")
    subp.set_defaults(func=msg_defs)
