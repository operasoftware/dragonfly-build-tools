INDENT = "  "

def escape_text_html(str): return str.replace("&", "&amp;").replace("<", "&lt;")

def escape_attr_html(str): return str.replace("\"", "&quot;")

class Node(object):
    ELEMENT = 1
    TEXT = 2
    ROOT = 3
    type = 0
    parent = None

    def insert_before(self, node):
        if node.parent: node.parent.remove(node)
        children = self.parent.children
        children.insert(children.index(self), node)
        node.parent = self.parent
        return node

    def insert_after(self, node):
        try: self.next.insert_before(node)
        except AttributeError: self.parent.append(node)
        return node

    @property
    def depth(self):
        depth = 0
        node = self
        while node.parent:
            depth += 1
            node = node.parent
        return depth

    @property
    def next(self):
        try:
            children = self.parent.children
            return children[children.index(self) + 1]
        except (AttributeError, IndexError): return None

    @property
    def previous(self):
        try:
            children = self.parent.children
            return children[children.index(self) - 1]
        except (AttributeError, IndexError): return None

    @property
    def is_text(self): return self.type == Node.TEXT

    @property
    def is_element(self): return self.type == Node.ELEMENT

    @property
    def is_root(self): return self.type == Node.ROOT

    def __str__(self):
        return self.serialize(-1)

class Text(Node):
    type = Node.TEXT
    name = "#text"

    def __init__(self, value=""):
        self.value = value

    def split(self, pos):
        text = Text(self.value[pos:])
        self.insert_after(text)
        self.value = self.value[0:pos]
        return text

    def serialize(self, initial_depth=0):
        return escape_text_html(self.value)

class Element(Node):
    type = Node.ELEMENT
    BLOCKLEVELS = ["ul", "li", "div", "p", "h2", "pre", "ol", "table", "tr", "td", "th"]

    def __init__(self, name, text=""):
        self.children = []
        self.name = name
        self.attrs = {}
        if text: self.append(Text(text))

    def append(self, node):
        if node.parent: node.parent.remove(node)
        node.parent = self
        self.children.append(node)
        return node

    def remove(self, node):
        try: self.children.pop(self.children.index(node))
        except IndexError: pass
        return node

    def normalize(self):
        node = self.first_child
        text_node = None
        while node:
            if node.is_text:
                if text_node:
                    text_node.value += node.parent.remove(node).value
                    node = text_node
                else: text_node = node
            else: text_node = None
            node = node.next

    def set_attr(self, key, value):
        self.attrs[key] = value

    @property
    def first_child(self):
        try: return self.children[0]
        except IndexError: return None

    @property
    def is_blocklevel(self):
        return self.name in self.BLOCKLEVELS

    @property
    def contains_blocklevel(self):
        for child in self.children:
            if child.is_element and (child.is_blocklevel or child.contains_blocklevel):
                return True
        return False

    @property
    def text_content(self):
        text = []
        for child in self.children:
            if child.is_text: text.append(child.value)
            elif child.is_element: text.append(child.text_content)
        return "".join(text)

    @text_content.setter
    def text_content(self, value):
        self.children = [Text(value)]

    def serialize(self, initial_depth=0):
        attrs = "".join((" %s=\"%s\"" % (key, escape_attr_html(value)) for key, value in self.attrs.items()))
        content = "".join((child.serialize(initial_depth) for child in self.children))
        name = self.name
        indent = (initial_depth + self.depth) * INDENT
        if self.contains_blocklevel:
            return "\n%s<%s%s>%s\n%s</%s>" % (indent, name, attrs, content, indent, name)
        if self.is_blocklevel:
            return "\n%s<%s%s>%s</%s>" % (indent, self.name, attrs, content, self.name)
        return "<%s%s>%s</%s>" % (self.name, attrs, content, self.name)

class Root(Element):
    type = Node.ROOT
    name = "#root"

    def __init__(self):
        self.children = []

    def serialize(self, initial_depth=0):
        return "".join((child.serialize(initial_depth) for child in self.children))
