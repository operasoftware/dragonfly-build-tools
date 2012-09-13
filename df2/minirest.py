import re
import node

class ParseError(Exception):
    def __init__(self, lines):
        self.lines = lines
    def __str__(self):
        return "No processor for %s\n" % "\t\n".join(self.lines)

def get_doc_lines(path):
    with open(path, "rb") as f:  return f.readlines()

def reg_exp(*args): return re.compile("".join(list(args)))

re_empty = reg_exp(r"^\s*$")
def is_empty(line): return re_empty.match(line)

class HeadProcessor(object):
    re = reg_exp(r"[\-\*]+$")
    name = "h2"

    def process(self, lines, ctx_node):
        count = len(lines)
        if len(lines) > 1 and self.re.match(lines[1]):
            ctx_node.append(node.Element(self.name, lines.pop(0).rstrip() + " "))
            lines.pop(0)
        return len(lines) < count

class ListProcessor(object):
    re = reg_exp(r"([ \t]*)([*\-+])? +")
    INDENT = 1
    BULLET = 2
    container = "ul"
    item_name = "li"

    def process(self, lines, ctx_node, depth=-1):
        count = len(lines)
        container = None
        while lines:
            if depth > -1 and is_empty(lines[0]):
                lines.pop(0)
                break
            match = self.re.match(lines[0])
            if match:
                if match.group(self.BULLET):
                    new_depth = match.end(self.INDENT)
                    if  new_depth > depth:
                        if not container:
                            container = ctx_node.append(node.Element(self.container))
                        line = lines.pop(0)[match.end():].rstrip() + " "
                        li = container.append(node.Element(self.item_name, line))
                        self.process(lines, li, new_depth)
                    else: break
                else:
                    line = lines.pop(0)[match.end():].rstrip() + " "
                    ctx_node.append(node.Text(line))
            else: break
        ctx_node.normalize()
        return len(lines) < count

class OrderedListProcessor(ListProcessor):
    re = reg_exp(r"([ \t]*)((?:\d+|#)\.)? +")
    INDENT = 1
    BULLET = 2
    container = "ol"
    item_name = "li"

class DefinitionListProcessor(object):
    re = reg_exp(r"([ \t]+)|(?::([^ :]+:))")
    TERM = 2

    def process(self, lines, ctx_node, depth=-1):
        count = len(lines)
        table = None
        row = None
        td = None
        while lines:
            if row and is_empty(lines[0]):
                lines.pop(0)
                if td: td.normalize()
                row = td = None
                continue
            match = self.re.match(lines[0])
            if match:
                term = match.group(self.TERM)
                if term:
                    if not table: table = ctx_node.append(node.Element("table"))
                    row = table.append(node.Element("tr"))
                    row.append(node.Element("td")).append(node.Element("strong", term))
                    td = row.append(node.Element("td"))
                    text = lines.pop(0)[match.end():].rstrip() + " "
                    if text: td.append(node.Text(text))
                else:
                    if not table: break
                    if not td:
                        row = table.append(node.Element("tr"))
                        row.append(node.Element("td"))
                        td = row.append(node.Element("td"))
                    td.append(node.Text(lines.pop(0).strip() + " "))
            else: break
        return len(lines) < count

class PreProcessor(object):
    re = reg_exp(r"::")

    def process(self, lines, ctx_node):
        count = len(lines)
        if self.re.match(lines[0]):
            lines.pop(0)
            pre = ctx_node.append(node.Element("pre"))
            while lines:
                if is_empty(lines[0]) or lines[0].startswith((" ", "\t")):
                    pre.append(node.Text(lines.pop(0)))
                else: break
        return len(lines) < count

class SinceProcessor(object):
    re = reg_exp(r"@since\s*([\d.]+)")
    VERSION = 1

    def process(self, lines, ctx_node):
        count = len(lines)
        match = self.re.match(lines[0])
        if match: ctx_node.append(node.Element("p", lines.pop(0)))
        return len(lines) < count

class ParagraphProcessor(object):
    re = reg_exp(r"(?!\s*$|@since|(?:[*\-+] ))")

    def process(self, lines, ctx_node):
        count = len(lines)
        p = None
        while lines:
            if is_empty(lines[0]):
                lines.pop(0)
                break
            if self.re.match(lines[0]):
                if not p: p = ctx_node.append(node.Element("p"))
                p.append(node.Text(lines.pop(0).rstrip() + " "))
                continue
            break
        return len(lines) < count

class TextProcessor(object):
    re = reg_exp(r"")
    name = ""
    START = None
    END = None
    REPLACE = None # str, str

    def unescape(self, text_node):
        if self.REPLACE: text_node.value = text_node.value.replace(*self.REPLACE)

    def handle(self, text_node, match):
        text_node.split(match.end())
        text = text_node.split(match.start())
        if self.START or self.END: text.value = text.value[self.START:self.END]
        self.unescape(text_node)
        element = node.Element(self.name)
        element.append(text)
        text_node.insert_after(element)
        return element

    def process(self, node):
        while node:
            if node.is_text:
                match = self.re.search(node.value)
                if match: node = self.handle(node, match)
                else: self.unescape(node)
            elif node.is_root or (node.is_element and node.is_blocklevel):
                self.process(node.first_child)
            node = node.next

class BoldTextProcessor(TextProcessor):
    re = reg_exp(r"(?<!\\)\*\*(?:[^ *])*\*\*")
    name = "b"
    START = 2
    END = -2
    REPLACE = r"\**", "**"

class CodeTextProcessor(TextProcessor):
    re = reg_exp(r"(?<!\\)``[^ `]*``")
    name = "code"
    START = 2
    END = -2
    REPLACE = r"\``", "``"

class EmTextProcessor(TextProcessor):
    re = reg_exp(r"(?<![\\*])\*[^ *]+\*")
    name = "em"
    START = 1
    END = -1
    REPLACE = r"\*", "*"

class SinceTextProcessor(TextProcessor):
    re = reg_exp(r"@since(\s*[\d.]+)")
    name = "span"
    START = 6
    END = None
    REPLACE = None

    def handle(self, text_node, match):
        span = TextProcessor.handle(self, text_node, match)
        span.text_content = "Added in version " + span.text_content.strip()
        span.set_attr("class", "since-version")
        return span

class NoteTextProcessor(TextProcessor):
    re = reg_exp(r"@note")
    name = "span"
    START = None
    END = None
    REPLACE = None

    def handle(self, text_node, match):
        span = TextProcessor.handle(self, text_node, match)
        span.text_content = ""
        span.set_attr("class", "info")
        span.parent.set_attr("class", "note")
        return span

class LinkTextProcessor(TextProcessor):
    re = reg_exp(r"[^ ]{4,5}://[^ ]+")
    name = "a"
    START = None
    END = None
    REPLACE = None

    def handle(self, text_node, match):
        a = TextProcessor.handle(self, text_node, match)
        a.set_attr("href", a.text_content)
        return a

class SpecialTextProcessor(TextProcessor):
    re = reg_exp(r"(?<!\\)`[^ `]*`")
    name = "span"
    START = 1
    END = -1
    REPLACE = r"\`", "`"

    def handle(self, text_node, match):
        span = TextProcessor.handle(self, text_node, match)
        # TODO handle domain specific token
        span.set_attr("class", "domain-specific")
        return span

block_processors = [HeadProcessor(),
                    ListProcessor(),
                    OrderedListProcessor(),
                    DefinitionListProcessor(),
                    PreProcessor(),
                    SinceProcessor(),
                    ParagraphProcessor()]
text_processors = [BoldTextProcessor(),
                   EmTextProcessor(),
                   CodeTextProcessor(),
                   SpecialTextProcessor(),
                   LinkTextProcessor(),
                   SinceTextProcessor(),
                   NoteTextProcessor()]

def process(lines):
    root = node.Root()
    while lines:
        count = len(lines)
        for processor in block_processors:
            if processor.process(lines, root): break
        if lines and len(lines) == count: raise ParseError(lines)
    for processor in text_processors:
        processor.process(root)
    return root

def main():
    print process(get_doc_lines("doc"))

if __name__ == "__main__":
    main()
