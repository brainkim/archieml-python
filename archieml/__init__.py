import re
def get_in(d, path, default=None):
    for k in path:
        if type(d) == dict and k in d:
            d = d[k]
        else:
            d = default
            break
    return d

def set_in(d, path, value):
    for k in path[:-1]:
        if k not in d or type(d[k]) != dict:
            d[k] = {}
        d = d[k]
    d[path[-1]] = value

class Loader(object):
    START_KEY     = re.compile(r'^\s*(?P<key>[A-Za-z0-9\-_\.]+)[ \t\r]*:[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    COMMAND_KEY   = re.compile(r'^\s*:[ \t\r]*(?P<command>endskip|ignore|skip|end).*?(\n|\r|$)', re.IGNORECASE)
    ARRAY_ELEMENT = re.compile(r'^\s*\*[ \t\r]*(?P<value>.*(?:\n|\r|$))')
    SCOPE_PATTERN = re.compile(r'^\s*(?P<delimiter>\[|\{)[ \t\r]*(?P<flags>[\+\.]*)(?P<key>[A-Za-z0-9\-_\.]*)[ \t\r]*(?:\]|\}).*?(\n|\r|$)')

    def __init__(self, **options):
        self.result = {}
        self.stack = []
        self.push_scope()

        self.buffer_key = None
        self.buffer_value = ''

        self.is_skipping = False
        self.done_parsing = False
    
    def push_scope(self, path=[], flags=''):
        self.stack.append({
            'path': path,
            'flags': flags,
            'is_simple': False,
            'array_start_key': None,
        })

    def pop_scope(self):
        if len(self.stack) > 1: self.stack.pop()

    def loads(self, aml, **options):
        lines = aml.splitlines(True)
        for line in lines:
            scope = self.stack[-1]
            if self.done_parsing:
                break
            elif self.COMMAND_KEY.match(line):
                m = self.COMMAND_KEY.match(line)
                self.load_command(m.group('command'))
            elif not self.is_skipping\
                    and not scope['is_simple']\
                    and self.START_KEY.match(line):
                m = self.START_KEY.match(line)
                self.load_key(m.group('key'), m.group('value'))
            elif not self.is_skipping\
                    and scope['array_start_key'] is None\
                    and type(get_in(self.data, scope['path'])) == list\
                    and self.ARRAY_ELEMENT.match(line):
                m = self.ARRAY_ELEMENT.match(line)
                self.load_array_element(m.group('value'))
            elif not self.is_skipping and self.SCOPE_PATTERN.match(line):
                m = self.SCOPE_PATTERN.match(line)
                self.load_scope(m.group('delimiter'), m.group('flags'), m.group('key'))
            else:
                self.load_text(line)
        return self.data

    def flush_buffer(self, key=None, value=''):
        self.buffer_key = key
        self.buffer_value = value

    def load_command(self, command):
        command = command.lower()
        if self.is_skipping and not (command == 'endskip' or command == 'ignore'):
            pass
        elif command == 'end' and self.buffer_value:
            scope = self.stack[-1]
            current = get_in(self.data, scope['path'])
            if scope['is_simple']:
                current[-1] = self.buffer_value.rstrip()
            else:
                if type(current) == list:
                    current = current[-1]
                set_in(current, self.buffer_key.split('.'), self.buffer_value.rstrip())
        elif command == 'ignore':
            self.done_parsing = True
        elif command == 'skip':
            self.is_skipping = True
        elif command == 'endskip':
            self.is_skipping = False
        self.flush_buffer()

    def load_key(self, key, value):
        self.flush_buffer()
        self.buffer_key = key
        self.buffer_value = value

        scope = self.stack[-1]
        current = get_in(self.data, scope['path'])
        if type(current) == list:
            if scope['array_start_key'] is None:
                scope['array_start_key'] = key

            if key == scope['array_start_key']:
                current.append({})
            current = current[-1]
        set_in(self.data, scope['path'], value.rstrip())

    def load_array_element(self, value):
        self.flush_buffer()
        self.buffer_value = value

        scope = self.stack[-1]
        scope['is_simple'] = True
        current = get_in(self.data, scope['path'])
        current.append(value.rstrip())

    def load_scope(self, delimiter, flags, key):
        self.flush_buffer()
        if key == '':
            self.pop_scope()
        else:
            path = key.split('.')
            if delimiter == '[' and '.' in flags:
                path = self.stack[-1]['path'] + path
            empty_coll = {} if delimiter == '{' else []
            set_in(self.data, path, empty_coll)
            self.push_scope(path=path, flags=flags)

    def load_text(self, text):
        self.buffer_value += text

def loads(aml):
	loader = Loader()
	return loader.load(aml)

def load(f):
	return loads(f.read())
