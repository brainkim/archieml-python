import re
from collections import OrderedDict
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

class Scope(object):
    def __init__(self, key=None, brace='{', flags='', old_scope=None):
        assert brace == '{' or brace == '['
        self.brace = brace

        self.is_nested   = '.' in flags
        self.is_freeform = '+' in flags

        if not key:
            self.path = []
        elif self.is_nested and old_scope is not None:
            self.path = old_scope.get_path(key)
            if old_scope.is_freeform:
                self.path[-1] = 'value'
        else:
            self.path = key.split('.')

        if brace == '[':
            self.index = 0
        else:
            self.index = None

        self.first_key = None
        self.is_simple = False

    def update_index(self, key):
        if self.brace == '[':
            if self.first_key is None:
                self.first_key = key
                return False
            elif self.first_key == key:
                self.index += 1
                return True
        return False

    def get_path(self, key):
        if isinstance(key, int):
            path = self.path + [key]
            self.is_simple = (not self.is_freeform)
            self.index += 1
        else:
            if not self.is_freeform:
                path = key.split('.')
            else:
                path = [key]
            if self.brace == '[':
                path = self.path + [self.index] + path
            else:
                path = self.path + path
        return path

class Loader(object):
    WHITESPACE = u'\u0000\u0009\u000A\u000B\u000C\u000D\u0020\u00A0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u200B\u2028\u2029\u202F\u205F\u3000\uFEFF'

    # blacklist characters: "[\]{}:"
    SLUG_BLACKLIST = WHITESPACE + u'\u005B\u005C\u005D\u007B\u007D\u003A'
    KEY_PATTERN = re.compile(r'^\s*(?P<key>[^' + SLUG_BLACKLIST + r']+)[ \t\r]*:[ \t\r]*(?P<value>.*(?:\n|\r|$))', re.UNICODE)
    COMMAND_PATTERN = re.compile(r'^\s*:[ \t\r]*(?P<command>endskip|ignore|skip|end).*?(?:\n|\r|$)', re.IGNORECASE)
    ELEMENT_PATTERN = re.compile(r'^\s*\*[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    SCOPE_PATTERN = re.compile(r'^\s*(?P<brace>\[|\{)[ \t\r]*(?P<flags>[\+\.]{0,2})(?P<scope_key>[^' + SLUG_BLACKLIST + r']*(?:\.[\w-]+)*)[ \t\r]*(?:\]|\}).*?(?:\n|\r|$)', re.UNICODE)

    def __init__(self):
        self.data = OrderedDict()

        self.reset_buffer()

        self.initial_scope = Scope()
        self.stack = [self.initial_scope]

        self.is_skipping  = False
        self.done_parsing = False

    @property
    def current_scope(self):
        return self.stack[-1]

    def reset_buffer(self, key=None, value=''):
        self.buffer_key   = key
        self.buffer_value = value

    def prepare_data(self, path):
        data = self.data
        for i, k in enumerate(path[:-1]):
            if isinstance(data, list):
                try:
                    data = data[k]
                except IndexError:
                    data.append(OrderedDict())
                    data = data[k]
            elif isinstance(data, dict):
                if k not in data:
                    data[k] = OrderedDict()
                else:
                    next_k = path[i+1]
                    try:
                        data[k][next_k]
                    except (KeyError, IndexError):
                        pass
                    except TypeError:
                        data[k] = OrderedDict()
                data = data[k]
        return data

    def set_value(self, key, value, use_scope=True):
        if use_scope:
            path = self.current_scope.get_path(key)
        else:
            path = self.initial_scope.get_path(key)

        data = self.prepare_data(path)
        k = path[-1]
        if isinstance(data, dict):
            if value == OrderedDict() and isinstance(data.get(k), dict):
                pass
            else:
                data[k] = value
        elif isinstance(data, list):
            try:
                data[k] = value
            except IndexError:
                data.append(value)

    def load(self, fp):
        for line in fp:
            if hasattr(line, 'decode') and not isinstance(line, unicode):
                # This is a byte string, decode it
                line = line.decode('utf-8-sig')

            scope = self.current_scope

            if self.done_parsing:
                break
            elif line[0] == '\\':
                self.load_text(line)
            elif self.COMMAND_PATTERN.match(line):
                m = self.COMMAND_PATTERN.match(line)
                self.load_command(m.group('command'))
            elif (not self.is_skipping and not scope.is_simple and
                    self.KEY_PATTERN.match(line)):
                m = self.KEY_PATTERN.match(line)
                self.load_key(m.group('key'), m.group('value'))
            elif (not self.is_skipping and
                    (scope.is_simple or
                        (scope.first_key is None and scope.brace == '[' and not scope.is_freeform)) and
                    self.ELEMENT_PATTERN.match(line)):
                m = self.ELEMENT_PATTERN.match(line)
                self.load_element(m.group('value'))
            elif not self.is_skipping and self.SCOPE_PATTERN.match(line):
                m = self.SCOPE_PATTERN.match(line)
                self.load_scope(m.group('brace'), m.group('flags'), m.group('scope_key'))
            elif not self.is_skipping:
                self.load_text(line)

        return self.data

    def load_command(self, command):
        command = command.lower()
        if self.is_skipping and not (command == 'endskip' or command == 'ignore'):
            pass
        elif command == 'end' and self.buffer_key is not None and self.buffer_value:
            self.set_value(self.buffer_key, self.buffer_value.strip())
        elif command == 'ignore':
            self.done_parsing = True
        elif command == 'skip':
            self.is_skipping = True
        elif command == 'endskip':
            self.is_skipping = False
        self.reset_buffer()

    def load_key(self, key, value):
        if self.current_scope.is_freeform:
            self.set_value(
                self.current_scope.index, OrderedDict([
                    ('type', key), ('value', value.strip())
                ])
            )
        else:
            self.current_scope.update_index(key)
            self.set_value(key, value.strip())
        self.reset_buffer(key, value)

    def load_element(self, value):
        key = self.current_scope.index
        self.set_value(key, value.strip())
        self.reset_buffer(key, value)

    def load_scope(self, brace, flags, scope_key):
        if scope_key == '' and len(self.stack) > 1:
            self.stack.pop()
        else:
            old_scope = self.current_scope
            new_scope = Scope(scope_key, brace=brace, flags=flags, old_scope=old_scope)
            if new_scope.is_nested:
                old_scope.update_index(scope_key)

            if old_scope.is_freeform and new_scope.is_nested:
                self.set_value(
                    old_scope.index,
                    OrderedDict([
                        ('type', scope_key),
                        ('value',  OrderedDict() if brace == '{' else [])
                    ])
                )
            else:
                self.set_value(
                    scope_key,
                    OrderedDict() if brace == '{' else [],
                    use_scope=new_scope.is_nested
                )

            # See: https://github.com/newsdev/archieml-js/issues/17
            if len(self.stack) > 1 and not new_scope.is_nested:
                self.stack[-1] = new_scope
            else:
                self.stack.append(new_scope)
        self.reset_buffer()

    def load_text(self, text):
        if self.current_scope.is_freeform and text.strip():
            self.set_value(
                self.current_scope.index, OrderedDict([
                    ('type', 'text'), ('value', text.strip())
                ])
            )
        else:
            self.buffer_value += re.sub(r'^(\s*)\\', r'\1', text)

def load(fp):
    return Loader().load(fp)

def loads(aml):
    return Loader().load(StringIO(aml))
