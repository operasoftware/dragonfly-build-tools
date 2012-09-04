import re
import protoobjects

WS = r"\s*"
WS_PLUS = r"\s+"
EQ_SIGN = r"\s*=\s*"
SEMIC = r";"
OPTIONAL = r"?"
NUMBER = r"(\d+)"
STRING = r"(\"(?:[^\\\"]|\\\.)*\")"
IDENT = r"([A-Za-z0-9._]+)"
# e.g.: /**
#         * documentation
#         */
DOC = r"(/\*(?:[^*]*|\*+[^/])*\*+/)"
COMMENT = r"\s*(//.*)"

def reg_exp(*args): return re.compile("".join(list(args)))

class Buffer(object):
    def __init__(self):
        self.doc = ""
        self.comment = ""

    def reset(self):
        self.doc = ""
        self.comment = ""

class ParseError(Exception):
    def __init__(self, line_no, line):
        self.line_no = line_no
        self.line = line

    def __str__(self):
        return "ParseError: could not parse line %s:\n\n\t%s" % (self.line_no, self.line)

class Global:
    pass

class Syntax(object):
    # e.g: syntax = scope;
    regexp = reg_exp(WS, r"syntax", EQ_SIGN, r"\"?", IDENT, r"\"?", WS, SEMIC, WS)

    @staticmethod
    def handler(scope, buffer, match):
        SYNTAX = 1
        p = match.group
        scope.syntax = p(SYNTAX)
        return scope

class Message(object):
    # e.g.: message CssStylesheetList {
    regexp = reg_exp(WS, r"message", WS, IDENT, WS, r"{")

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        p = match.group
        comment = buffer.comment
        doc = buffer.doc
        message = protoobjects.Message(p(NAME), doc, comment, scope)
        scope.messages.append(message)
        buffer.reset()
        return message

class End(object):
    regexp = reg_exp(WS, r"[\}\]]", WS, SEMIC, OPTIONAL)

    @staticmethod
    def handler(scope, buffer, match):
        return None

class Service(object):
    # e.g.: service EcmascriptDebugger {
    regexp = reg_exp(WS, r"service", WS, IDENT, WS, r"{")

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        p = match.group
        comment = buffer.comment
        doc = buffer.doc
        service = protoobjects.Service(p(NAME), doc, comment, scope)
        scope.service = service
        buffer.reset()
        return service

class Doc(object):
    regexp = reg_exp(WS, DOC, WS)

    @staticmethod
    def handler(scope, buffer, match):
        DOC = 1
        p = match.group
        buffer.doc = p(DOC)
        return scope

class Comment(object):
    regexp = reg_exp(COMMENT)

    @staticmethod
    def handler(scope, buffer, match):
        COMMENT = 1
        p = match.group
        buffer.doc = p(COMMENT)
        return scope

class Field(object):
    # e.g.: optional ObjectValue objectValue = 4;
    regexp = reg_exp(WS, r"(required|repeated|optional)", WS, IDENT, WS_PLUS, IDENT,
                     EQ_SIGN, NUMBER, WS, r"(\[|;)", COMMENT, OPTIONAL)

    @staticmethod
    def handler(scope, buffer, match):
        Q = 1
        TYPE = 2
        NAME = 3
        KEY = 4
        OPTION_OR_SEMICOLON  = 5
        COMMENT = 6
        p = match.group
        comment = buffer.comment or p(COMMENT)
        doc = buffer.doc
        field = protoobjects.Field(p(Q), p(TYPE), p(NAME), p(KEY), comment, doc, scope)
        scope.fields.append(field);
        buffer.reset()
        return scope if (p(OPTION_OR_SEMICOLON) == ";") else field

class FieldOption(object):
    # e.g default = false
    regexp = reg_exp(WS, r"(?:,)", OPTIONAL, WS, DOC, OPTIONAL, WS, IDENT,
                     EQ_SIGN, r"(?:", IDENT, r"|", STRING, r")", WS, DOC, OPTIONAL, WS)
    @staticmethod
    def handler(scope, buffer, match):
        DOC1 = 1
        NAME = 2
        IDENT = 3
        STRING = 4
        DOC2 = 5
        p = match.group
        value = p(IDENT) or p(STRING)
        doc = p(DOC1) or p(DOC2)
        setattr(scope.options, p(NAME), protoobjects.FieldOption(value, doc))
        return scope

class OptionsEnd(object):
    regexp = reg_exp(WS, r"\]", WS, SEMIC, OPTIONAL, WS)

    @staticmethod
    def handler(scope, buffer, match):
        return None

class Option(object):
    # e.g.: option (cpp_hfile) = "modules/scope/src/scope_ecmascript_debugger.h";
    regexp = reg_exp(WS, r"option", WS, r"\(", IDENT, r"\)", EQ_SIGN,
                     r"(?:", IDENT, r"|", STRING, r")", WS, SEMIC, OPTIONAL, WS)

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        IDENT = 2
        STRING = 3
        p = match.group
        value = p(IDENT) or p(STRING)
        setattr(scope.options, p(NAME), protoobjects.FieldOption(value))
        return scope

class Command(object):
    # e.g.: command ListRuntimes(RuntimeSelection) returns (RuntimeList) = 1;
    regexp = reg_exp(WS, r"command", WS, IDENT, WS, r"\(", IDENT, r"\)", WS, r"returns", WS,
                     r"\(", IDENT, r"\)", EQ_SIGN, NUMBER, WS, r"(?:;|(\{))", WS)

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        REQ_ARG = 2
        RES_ARG = 3
        KEY = 4
        SCOPE_OPEN = 5
        p = match.group
        comment = buffer.comment
        doc = buffer.doc
        command = protoobjects.Command(p(NAME), p(REQ_ARG), p(RES_ARG), p(KEY), comment, doc, scope)
        scope.commands.append(command)
        buffer.reset()
        return command if match.group(SCOPE_OPEN) else scope

class Event(object):
    # e.g.: event OnRuntimeStarted returns (RuntimeInfo) = 14;
    regexp = reg_exp(WS, r"event", WS, IDENT, WS, r"returns", WS,
                     r"\(", IDENT, r"\)", EQ_SIGN, NUMBER, WS, SEMIC, WS)

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        RES_ARG = 2
        KEY = 3
        p = match.group
        comment = buffer.comment
        doc = buffer.doc
        scope.events.append(protoobjects.Event(p(NAME), p(RES_ARG), p(KEY), comment, doc, scope))
        buffer.reset()
        return scope

class Enum(object):
    # e.g.: enum Type {
    regexp = reg_exp(WS, r"enum", WS, IDENT, WS, r"{")

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        p = match.group
        comment = buffer.comment
        doc = buffer.doc
        enum = protoobjects.Enum(p(NAME), doc, comment, scope)
        scope.enums.append(enum)
        buffer.reset()
        return enum

class EnumField(object):
    # e.g.: UNDEFINED = 0;
    regexp = reg_exp(WS, r"([A-Z_0-9]+)", EQ_SIGN, NUMBER, WS, SEMIC, WS)

    @staticmethod
    def handler(scope, buffer, match):
        NAME = 1
        KEY = 2
        p = match.group
        comment = buffer.comment
        doc = buffer.doc
        scope.fields.append(protoobjects.EnumField(p(NAME), p(KEY), doc, comment))
        buffer.reset()
        return scope

Global.states = [Syntax, Message, Enum, Service, Doc, Comment]
Message.states = [Message, Enum, Field, Doc, Comment, End]
Service.states = [Option, Command, Event, Doc, Comment, End]
Enum.states = [EnumField, Doc, Comment, End]
Field.states = [FieldOption, Option, End]
Command.states = [FieldOption, Option, End]

def parse(source):
    global_scope = protoobjects.Global()
    cur_state = Global
    scope = global_scope
    buffer = Buffer()
    cursor = 0
    state_stack = []
    while True:
        match = None
        for state in cur_state.states:
            match = state.regexp.match(source, cursor)
            if match:
                new_scope = state.handler(scope, buffer, match)
                cursor += len(match.group(0))
                if (new_scope == None):
                    cur_state, scope = state_stack.pop()
                elif (not new_scope == scope):
                    state_stack.append((cur_state, scope))
                    cur_state = state
                    scope = new_scope
                break

        if not match:
            if cursor < len(source):
                raise ParseError(source[0:cursor].count("\n") + 1, source[cursor:source.find("\n", cursor + 1)])

            return global_scope
