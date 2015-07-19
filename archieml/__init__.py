import re
from StringIO import StringIO

def _set_in(data, path, value):
    assert type(path) == list and len(path) > 0

    data = data
    for k in path[:-1]:
        if type(k) == int:
            try:
                data = data[k]
            except Exception as e:
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
    def __init__(self, path, old_path=None, brace='{', flags=''):
        self.brace = brace

        self.is_nesting  = '.' in flags
        self.is_freeform = '+' in flags

        if brace == '[':
            if self.is_nesting and old_path is not None:
                self.path = old_path + path + [0]
            else:
                self.path = path + [0]
        else:
            self.path = path

        self.first_key = None
        self.is_simple = False

    def increment(self):
        assert type(self.path[-1]) == int
        self.path[-1] += 1

class Loader(object):
    COMMAND_PATTERN = re.compile(r'^\s*:[ \t\r]*(?P<command>endskip|ignore|skip|end).*?(?:\n|\r|$)', re.IGNORECASE)
    KEY_PATTERN     = re.compile(r'^\s*(?P<key>[A-Za-z0-9\-_\.]+)[ \t\r]*:[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    ELEMENT_PATTERN = re.compile(r'^\s*\*[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    SCOPE_PATTERN   = re.compile(r'^\s*(?P<brace>\[|\{)[ \t\r]*(?P<flags>[\+\.]{0,2})(?P<key>[A-Za-z0-9\-_\.]*)[ \t\r]*(?:\]|\}).*?(?:\n|\r|$)')

    def __init__(self, **options):
        self.data = {}

        self.reset_buffer()

        self.stack = []
        self.stack.append(Scope(path=[]))

        self.is_skipping  = False
        self.done_parsing = False

    def reset_buffer(self, path=None, value=''):
        self.buffer_path  = path 
        self.buffer_value = value

    @property
    def current_scope(self):
        return self.stack[-1]

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
                self.load_scope(m.group('brace'), m.group('flags'), m.group('key'))

            elif not self.is_skipping:
                self.load_text(line)

        return self.data
    
    def load_command(self, command):
        command = command.lower()
        if self.is_skipping and not (command == 'endskip' or command == 'ignore'):
            pass
        elif command == 'end' and self.buffer_path and self.buffer_value:
            _set_in(self.data, self.buffer_path, self.buffer_value.strip())
        elif command == 'ignore':
            self.done_parsing = True
        elif command == 'skip':
            self.is_skipping = True
        elif command == 'endskip':
            self.is_skipping = False
        self.reset_buffer()

    def load_key(self, key, value):
        scope = self.current_scope
        if scope.first_key is None:
            scope.first_key = key
        elif scope.brace == '[' and key == scope.first_key:
            scope.increment()
        path = scope.path + key.split('.')
        _set_in(self.data, scope.path + key.split('.'), value.strip())
        self.reset_buffer(path=path, value=value)

    def load_element(self, value):
        scope = self.current_scope
        scope.is_simple = True
        _set_in(self.data, scope.path, value.strip())
        self.reset_buffer(path=list(scope.path), value=value)
        scope.increment()

    def _push_scope(self, scope):
        self.stack.append(scope)

    def _pop_scope(self):
        if len(self.stack) > 1:
            return self.stack.pop()

    def load_scope(self, brace, flags, scope_key):
        self.reset_buffer()
        if scope_key == '':
            self._pop_scope()
        else:
            old_scope = self.current_scope
            path = scope_key.split('.')
            new_scope = Scope(path, old_path=old_scope.path, brace=brace, flags=flags)

            if new_scope.is_nesting and old_scope.first_key is None:
                old_scope.first_key = scope_key
            elif old_scope.brace == '[' and old_scope.first_key == scope_key:
                old_scope.increment()

            if new_scope.is_nesting:
                base_path = old_scope.path + path
            else:
                base_path = path

            initial_value = {} if brace == '{' else []

            _set_in(self.data, base_path, initial_value)

            self._push_scope(new_scope)

    def load_text(self, text):
        self.buffer_value += re.sub(r'^(\s*)\\', r'\1', text)

def load(f):
    return Loader().load(f)

def loads(aml):
    return Loader().load(StringIO(aml))
