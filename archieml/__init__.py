import re
from StringIO import StringIO

def _set_in(data, path, value):
    assert type(path) == list and len(path) > 0

    data = data
    for k in path[:-1]:
        if type(k) == int:
            try:
                data = data[k]
            except IndexError:
                data.append({})
                data = data[k]
        elif type(k) == str or type(k) == unicode:
            if k not in data or type(data[k]) == str:
                data[k] = {}
            data = data[k]
        else:
            raise TypeError("element in path which is not int or string: {}".format(path))

    try:
        if value == {} and type(data) == dict and type(data.get(path[-1])) == dict:
            pass
        else:
            data[path[-1]] = value
    except IndexError:
        data.append(None)
        data[path[-1]] = value

class Scope(object):
    def __init__(self, key, brace='{', flags='', old_scope=None):
        self.brace = brace

        self.is_nesting  = '.' in flags
        self.is_freeform = '+' in flags

        if old_scope is not None and self.is_nesting:
            old_scope.add_key(key)

        if key:
            key_path = key.split('.')
        else:
            key_path = []

        if brace == '[':
            if self.is_nesting and old_scope is not None and old_scope.path:
                self.path = old_scope.path + [old_scope.index] + key_path
            else:
                self.path = key_path
            self.index = 0

        else:
            self.path = key_path
            self.index = None

        self.first_key = None
        self.is_simple = False


    def increment(self):
        assert self.index is not None
        self.index += 1

    def resolve_key(self, key):
        pass

    def add_key(self, key):
        if self.first_key is None:
            self.first_key = key
        elif self.brace == '[' and self.first_key == key:
            self.increment()

class Loader(object):
    COMMAND_PATTERN = re.compile(r'^\s*:[ \t\r]*(?P<command>endskip|ignore|skip|end).*?(?:\n|\r|$)', re.IGNORECASE)
    KEY_PATTERN     = re.compile(r'^\s*(?P<key>[A-Za-z0-9\-_]+(?:\.[A-Za-z0-9\-_]+)*)[ \t\r]*:[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    ELEMENT_PATTERN = re.compile(r'^\s*\*[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    SCOPE_PATTERN   = re.compile(r'^\s*(?P<brace>\[|\{)[ \t\r]*(?P<flags>[\+\.]{0,2})(?P<scope_key>[A-Za-z0-9\-_]*(?:\.[A-Za-z0-9\-_]+)*)[ \t\r]*(?:\]|\}).*?(?:\n|\r|$)')

    def __init__(self, **options):
        self.data = {}

        self.reset_buffer()

        self.stack = []
        self.stack.append(Scope(key=''))

        self.is_skipping  = False
        self.done_parsing = False

    def reset_buffer(self, key=None, value=''):
        self.buffer_key   = key
        self.buffer_value = value

    @property
    def current_scope(self):
        return self.stack[-1]
    
    def set_value(self, key, value):
        data  = self.data
        scope = self.current_scope

        if type(key) == int:
            path = scope.path + [key]
        else:
            path = key.split('.')
            if scope.brace == '[':
                path = scope.path + [scope.index] + path
            else:
                path = scope.path + path

        for k in path[:-1]:
            if type(k) == int:
                try:
                    data = data[k]
                except IndexError:
                    data.append({})
                    data = data[k]
            elif type(k) == str or type(k) == unicode:
                if k not in data or type(data[k]) == str:
                    data[k] = {}
                data = data[k]
            else:
                raise TypeError("element in path which is not int or string: {}".format(path))

        try:
            if value == {} and type(data) == dict and type(data.get(path[-1])) == dict:
                pass
            else:
                data[path[-1]] = value
        except IndexError:
            data.append(None)
            data[path[-1]] = value

    def load(self, f, **options):
        for line in f:
            scope = self.current_scope

            if self.done_parsing:
                break

            elif self.COMMAND_PATTERN.match(line):
                m = self.COMMAND_PATTERN.match(line)
                self.load_command(m.group('command'))

            elif not self.is_skipping\
                    and not scope.is_simple\
                    and self.KEY_PATTERN.match(line):
                m = self.KEY_PATTERN.match(line)
                self.load_key(m.group('key'), m.group('value'))

            elif not self.is_skipping\
                    and scope.first_key is None\
                    and scope.brace == '['\
                    and self.ELEMENT_PATTERN.match(line):
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
        scope = self.current_scope
        scope.add_key(key)

        self.set_value(key, value.strip())
        self.reset_buffer(key=key, value=value)

    def load_element(self, value):
        scope = self.current_scope
        scope.is_simple = True
        self.set_value(scope.index, value.strip())
        self.reset_buffer(key=scope.index, value=value)
        scope.increment()

    def push_scope(self, scope):
        self.stack.append(scope)

    def pop_scope(self):
        if len(self.stack) > 1:
            return self.stack.pop()

    def load_scope(self, brace, flags, scope_key):
        if scope_key == '':
            self.pop_scope()
        else:
            old_scope = self.current_scope
            new_scope = Scope(scope_key, brace=brace, flags=flags, old_scope=old_scope)
            _set_in(self.data, new_scope.path, {} if brace == '{' else [])
            self.push_scope(new_scope)
        self.reset_buffer()

    def load_text(self, text):
        self.buffer_value += re.sub(r'^(\s*)\\', r'\1', text)

def load(f):
    return Loader().load(f)

def loads(aml):
    return Loader().load(StringIO(aml))
