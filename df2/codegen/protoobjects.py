import re

NUMBER = 1
BUFFER = 2
BOOLEAN = 3
MESSAGE = 4
ENUM = 5
COMMAND = 6
EVENT = 7
ENUM_FIELD = 8
PRIMITIVES = [NUMBER, BUFFER, BOOLEAN]

class TypeError(Exception):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "TypeError: %s" % self.name

class Type(object):
    sup_type = 0
    name = None

    @property
    def is_primitive(self): return self.sup_type in PRIMITIVES

    @property
    def is_message(self):
        return self.sup_type == MESSAGE

    @property
    def is_enum(self): return self.sup_type == ENUM

class UInt32(Type):
    sup_type = NUMBER
    name = "uint32"

class Bool(Type):
    sup_type = BOOLEAN
    name = "bool"

class String(Type):
    sup_type = BUFFER
    name = "string"

class Double(Type):
    sup_type = NUMBER
    name = "double"

class Int32(Type):
    sup_type = NUMBER
    name = "int32"

class Bytes(Type):
    sup_type = BUFFER
    name = "bytes"

class DocLines(object):
    _re_doc_lines = re.compile(r"(?:/\*+)?\r?\n[ \t]*\* ?/?")
    @property
    def doc_lines(self):
        return self._re_doc_lines.split(self.doc.strip())

class FieldOptions(object): pass

class FieldOption(object):
    def __init__(self, value, doc=""):
        self.value = value
        self.doc = doc

class Prop(object):
    def _get_obj(self, scope, props, name_chain):
        names = name_chain.split(".")
        while names:
            name = names.pop(0)
            scope = self._get_single_obj(scope, props, name)
        return scope

    def _get_single_obj(self, scope, props, name):
        while scope:
            for prop in props:
                for obj in getattr(scope, prop):
                    if obj.name == name:
                        return obj
            scope = scope.parent_scope
        raise TypeError(name)

class Field(Prop, DocLines):
    def __init__(self, q, type, name, key, comment, doc, scope):
        self.q = q
        self._type = type
        self.name = name
        self.key = key
        self.options = FieldOptions()
        self.comment = comment
        self.doc = doc
        self._scope = scope

    @property
    def type(self):
        return Type.primitives.get(self._type, None) or self._get_obj(self._scope, ["messages", "enums"], self._type)

    @property
    def full_type_name(self):
        return self._type

    @property
    def default_value(self):
        try: return self.options.default.value
        except AttributeError: return None

class Message(Type, DocLines):
    sup_type = MESSAGE
    def __init__(self, name, doc, comment, parent_scope):
        self.name = name;
        self.doc = doc;
        self.comment = comment;
        self.parent_scope = parent_scope;
        self.fields = [];
        self.messages = [];
        self.enums = [];

    def get_sub_messages(self, msgs=None):
        if msgs == None: msgs = []
        for field in self.fields:
            obj = field.type
            if obj.sup_type == MESSAGE:
                if not obj in msgs:
                    msgs.append(obj)
                    obj.get_sub_messages(msgs)
        return msgs

class Command(Type, Prop, DocLines):
    sup_type = COMMAND
    def __init__(self, name, request_arg, response_arg, key, comment, doc, scope):
        self.name = name
        self.key = key
        self._request_arg = request_arg
        self._response_arg = response_arg
        self.comment = comment
        self.doc = doc
        self.scope = scope
        #self.parent_scope = scope # TODO
        self.options = FieldOptions()

    @property
    def request_arg(self):
        return self._get_obj(self.scope.parent_scope, ["messages"], self._request_arg)

    @property
    def response_arg(self):
        return self._get_obj(self.scope.parent_scope, ["messages"], self._response_arg)

class Event(Type, Prop, DocLines):
    sup_type = EVENT
    def __init__(self, name, response_arg, key, comment, doc, scope):
        self.name = name
        self.key = key
        self._response_arg = response_arg
        self.comment = comment
        self.doc = doc
        self.scope = scope

    @property
    def response_arg(self):
        return self._get_obj(self.scope.parent_scope, ["messages"], self._response_arg)

class Enum(Type, DocLines):
    sup_type = ENUM
    def __init__(self, name, doc, comment, parent_scope):
        self.name = name
        self.doc = doc
        self.comment = comment
        self.parent_scope = parent_scope
        self.fields = []
        self.dict = {}

class EnumField(Type, DocLines):
    sup_type = ENUM_FIELD
    def __init__(self, name, key, doc, comment):
        self.name = name
        self.key = key
        self.doc = doc
        self.comment = comment

class Service(DocLines):
    MAJOR_VERSION = 0
    MINOR_VERSION = 1
    PATCH_VERSION = 2

    def __init__(self, name, doc, comment, parent_scope):
        self.name = name
        self.parent_scope = parent_scope
        self.commands = []
        self.events = []
        self.options = FieldOptions()
        self.doc = doc
        self.comment = comment

    def _set_version_array(self):
        self._version_array = map(int, self.version.split("."))
        if len(self._version_array) == 2: self._version_array.append(0)
        return self._version_array

    @property
    def version(self):
        try: return self.options.version.value.strip("\"")
        except AttributeError: return ""

    @property
    def major_version(self):
        try: return self._version_array[self.MAJOR_VERSION]
        except AttributeError: return self._set_version_array()[self.MAJOR_VERSION]

    @property
    def minor_version(self):
        try: return self._version_array[self.MINOR_VERSION]
        except AttributeError: return self._set_version_array()[self.MINOR_VERSION]

    @property
    def patch_version(self):
        try: return self._version_array[self.PATCH_VERSION]
        except AttributeError: return self._set_version_array()[self.PATCH_VERSION]

    @property
    def command_names(self):
        cmds = map(lambda c: c.name, self.commands)
        cmds.sort()
        return cmds

    @property
    def event_names(self):
        evs = map(lambda e: e.name, self.events)
        evs.sort()
        return evs

    def __getattr__(self, key):
        for t in [self.commands, self.events]:
            for m in t:
                if m.name == key: return m
        raise AttributeError, key

class Global(object):
    def __init__(self):
        self.syntax = ''
        self.messages = [Message("Default", None, None, None)]
        self.enums = []
        self.service = None
        self.options = FieldOptions()
        self.parent_scope = None

Type.primitives = (lambda gs: dict([(o.name, o()) for o in gs if getattr(o, "sup_type", None) in PRIMITIVES]))(globals().values())
