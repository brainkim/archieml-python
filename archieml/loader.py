import re
import json

class Scope(object):
	SIMPLE_ARRAY = 1
	COMPLEX_ARRAY = 2
	OBJECT = 3

	def __init__(self, path=[], scope_type=None):
		self.path = path
		self.scope_type = scope_type if scope_type is not None else self.OBJECT

class Loader(object):
	NEXT_LINE     = re.compile(r'.*((\r|\n)+)')
	START_KEY	  = re.compile(r'^\s*(?P<key>[A-Za-z0-9\-_\.]+)[ \t\r]*:[ \t\r]*(?P<value>.*(?:\n|\r|$))')
	COMMAND_KEY   = re.compile(r'^\s*:[ \t\r]*(?P<command>endskip|ignore|skip|end).*?(\n|\r|$)', re.IGNORECASE)
	ARRAY_ELEMENT = re.compile(r'^\s*\*[ \t\r]*(?P<value>.*(?:\n|\r|$))')
	SCOPE_PATTERN = re.compile(r'^\s*(?P<delimiter>\[|\{)[ \t\r]*(?P<flags>[\+\.]*)(?P<key>[A-Za-z0-9\-_\.]*)[ \t\r]*(?:\]|\}).*?(\n|\r|$)')

	def __init__(self, **options):
		# self.data is the data that can be returned at any moment during parsing. self.scope is an alias of self.data or nested list/dict
		# in self.data which represents what the item being mutated during parsing.
		self.data = self.scope = {}

		# the stack is used to keep track of list parsing and is composed of plain old dicts with the following keys:
		# `array` (the list being mutated)
		# `array_type` (simple | complex)
		# `first_key` (the first key seen in the document, which starts a new element, or is None if the list is simple
		# `scope` (the scope of the array)
		self.stack = []
		self.stack_scope = None

		# the buffer is used to store multi-line strings in the event that an :end command is found.
		self.buffer_key = None
		self.buffer_string = ''
		self.buffer_scope = None

		self.is_skipping = False
		self.done_parsing = False

		self.options = dict({}, **options)
	
	def load(self, aml, **options):
		options = dict(self.options, **options)
		while aml:
			if self.done_parsing:
				break
			elif self.COMMAND_KEY.match(aml):
				print "command"
				m = self.COMMAND_KEY.match(aml)
				self.parse_command_key(m.group('command').lower())
			elif not self.is_skipping and self.START_KEY.match(aml) and (not self.stack_scope or self.stack_scope.get('array_type') != 'simple'):
				print "start_key"
				m = self.START_KEY.match(aml)
				self.parse_start_key(m.group('key'), m.group('value'))
			elif not self.is_skipping and self.ARRAY_ELEMENT.match(aml) and self.stack_scope and self.stack_scope.get('array_type') == 'complex':
				print "array"
				m = self.ARRAY_ELEMENT.match(aml)
				self.parse_array_element(m.group('element'))
			elif not self.is_skipping and self.SCOPE_PATTERN.match(aml):
				print "scope"
				m = self.SCOPE_PATTERN.match(aml)
				self.parse_scope(m.group('delimiter'), m.group('flags'), m.group('key'))
			elif self.NEXT_LINE.match(aml):
				print "line"
				m = self.NEXT_LINE.match(aml)
				self.parse_text(m.group(0))
			else:
				print "otherwise"
				aml = ''

			if m:
				aml = aml[len(m.group(0)):]
		return self.data

	def parse_command_key(self, command):
		if self.is_skipping and not (command == 'endskip' or command == 'ignore'):
			pass
		elif command == 'end' and self.buffer_key:
			self.flush_buffer_into(self.buffer_key, replace=False)
		elif command == 'ignore':
			self.done_parsing = True
		elif command ==	'skip':
			self.is_skipping = True
		elif command == 'endskip':
			self.is_skipping = False
		self.flush_buffer()
	
	def parse_start_key(self, key, value):
		self.flush_buffer()
		self.increment_array_element(key)

		if self.stack_scope and '+' in self.stack_scope['flags']:
			key = 'value'

		self.buffer_key = key
		self.buffer_string = value

		self.flush_buffer_into(key, replace=True)
	
	def parse_array_element(self, value):
		self.flush_buffer()
		self.stack_scope['array_type'] = self.stack_scope.get('array_type', 'simple') 
		self.stack_scope['array'].append('')
		self.buffer_key = self.stack_scope['array']
		self.buffer_string = value
		self.flush_buffer_into(self.buffer_key, replace=True)
	
	def parse_scope(self, delimiter, flags, key):
		self.flush_buffer()
		if not key:
			if len(self.scope) != 0:
				frame = self.stack.pop()
				self.scope = frame['scope']
				self.stack_scope = self.stack[-1] if len(self.stack) != 0 else None
			else:
				self.scope = self.data
				self.stack_scope = None
		elif delimiter == '[' or delimiter == '{':
			nesting = False
			key_scope = self.data
			if '.' in key:
				self.increment_array_element(key)
				nesting = True
				if self.stack_scope is not None:
					key_scope =	self.scope

			key_bits = key.split('.')
			for bit in key_bits[:-1]:
				if type(self.buffer_scope.get(bit)) == str:
					self.buffer_scope[bit] = {}
				self.buffer_scope[bit] = self.buffer_scope.get(bit, {})
				self.buffer_scope = self.buffer_scope[bit]

			last_bit = key_bits[-1]
			if self.stack_scope is not None and '+' in self.stack_scope['flags'] and '.' in self.stack_scope['flags']:
				if delimiter == '[':
					last_bit = 'value'
				elif delimiter == '{':
					self.scope = self.scope['value'] = {}
			stack_scope_item = {
				'array': None,
				'array_type': None,
				'first_key': None,
				'flags': flags,
				'scope': self.scope,
			}
			if delimiter == '[':
				stack_scope_item['array'] = key_scope[last_bit] = []
				if nesting:
					self.stack.append(stack_scope_item)
				else:
					self.stack = [stack_scope_item]
				self.stack_scope = self.stack[-1]
			elif delimiter == '{':
				if nesting:
					self.stack.append(stack_scope_item)
				else:
					scope = key_scope.get(last_bit, None)
					if type(scope) == dict:
						self.scope = scope
						key_scope[last_bit] = scope
					else:
						self.scope = {}
						key_scope[last_bit] = scope
						self.stack = [stack_scope_item]
					self.stack_scope = self.stack[-1]

	def parse_text(self, text):
		if self.stack_scope and '+' in self.stack_scope['flags'] and re.search(r'[^\n\r\s]'):
			self.stack_scope['array'].append({'type': 'text', 'value': re.sub(r'(^\s*)|(\s*$)', '', text)})
		else:
			print json.dumps(self.buffer_string), json.dumps(text)
			self.buffer_string += text

	def increment_array_element(self, key):
		if self.stack_scope and self.stack_scope.get('array') is not None:
			self.stack_scope['array_type'] = self.stack_scope.get('array_type', 'complex')
			if self.stack_scope['array_type'] == 'simple':
				return

			first_key = self.stack_scope.get('first_key')
			if first_key is None or first_key == key:
				self.scope = {}
				self.stack_scope['array'].append(self.scope)
			self.stack_scope['first_key'] = self.stack_scope.get('first_key', key)

	def flush_buffer(self):
		result = self.buffer_string
		self.buffer_string = ''
		self.buffer_key = None
		return result

	def flush_buffer_into(self, key, replace=False):
		buffer_key = self.buffer_key
		value = self.flush_buffer()
		self.buffer_key = buffer_key
		if replace:
			value = value.lstrip()
			self.buffer_string = re.search(r'\s*$', value).group(0)
		else:
			value = re.sub(r'^(\s*)\\', r'\1', value)

		if type(key) == list:
			if replace:
				key[-1] = ''
			key[-1] += value.rstrip()
		else:
			key_bits = key.split('.')
			self.buffer_scope = self.scope

			for bit in key_bits[:-1]:
				if type(self.buffer_scope.get(bit)) == str:
					self.buffer_scope[bit] = {}
				self.buffer_scope[bit] = self.buffer_scope.get(bit, {})
				self.buffer_scope = self.buffer_scope[bit]
			if replace:
				self.buffer_scope[key_bits[-1]] = ''
			self.buffer_scope[key_bits[-1]] += self.buffer_scope.get(key_bits[-1], '') + value.rstrip()
