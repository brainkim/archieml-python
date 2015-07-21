import re
from StringIO import StringIO

class Scope(object):
    def __init__(self, key=None, brace='{', flags='', old_scope=None):
        assert brace == '{' or brace == '['
        self.brace = brace

        self.is_nested   = '.' in flags
        self.is_freeform = '+' in flags

        if not key:
            self.path = []
        elif self.is_nested and old_scope is not None:
            self.path = old_scope.resolve_key(key)
        else:
            self.path = key.split('.')

        if brace == '[':
            self.index = 0
        else:
            self.index = None

        self.first_key = None
        self.is_simple = False

    def register_key(self, key):
        if self.brace == '[':
            if self.first_key is None:
                self.first_key = key
            elif self.first_key == key:
                self.index += 1

    def resolve_key(self, key):
        if type(key) == int:
            path = self.path + [key]
            self.is_simple = True
            self.index += 1
        else:
            path = key.split('.')
            if self.brace == '[':
                path = self.path + [self.index] + path
            else:
                path = self.path + path
        return path

class Loader(object):
    COMMAND_PATTERN = re.compile(r'^\s*:[ \t\r]*(?P<command>endskip|ignore|skip|end).*?(?:\n|\r|$)', re.IGNORECASE)
    KEY_PATTERN     = re.compile(r'^\s*(?P<key>[A-Za-z0-9\-_]+(?:\.[A-Za-z0-9\-_]+)*)[ \t\r]*:[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    ELEMENT_PATTERN = re.compile(r'^\s*\*[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    SCOPE_PATTERN   = re.compile(r'^\s*(?P<brace>\[|\{)[ \t\r]*(?P<flags>[\+\.]{0,2})(?P<scope_key>[A-Za-z0-9\-_]*(?:\.[A-Za-z0-9\-_]+)*)[ \t\r]*(?:\]|\}).*?(?:\n|\r|$)')


    def __init__(self, **options):
        self.data = {}

        self.reset_buffer()

        self.initial_scope = Scope()
        self.stack = [self.initial_scope]

        self.is_skipping  = False
        self.done_parsing = False

    def reset_buffer(self, key=None, value=''):
        self.buffer_key   = key
        self.buffer_value = value

    @property
    def current_scope(self):
        return self.stack[-1]
    
    def set_value(self, key, value, use_scope=True):
        data = self.data
        if use_scope:
            path = self.current_scope.resolve_key(key)
        else:
            path = self.initial_scope.resolve_key(key)

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
                raise TypeError('element in path which is not int or string: {}'.format(path))

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
        self.current_scope.register_key(key)
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
                old_scope.register_key(scope_key)
            self.set_value(scope_key, {} if brace == '{' else [], use_scope=new_scope.is_nested)
            self.stack.append(new_scope)
        self.reset_buffer()

    def load_text(self, text):
        self.buffer_value += re.sub(r'^(\s*)\\', r'\1', text)

def load(f):
    return Loader().load(f)

def loads(aml):
    return Loader().load(StringIO(aml))
