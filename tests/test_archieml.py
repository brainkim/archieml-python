import os
import glob
import json
import unittest

import archieml

class TestArchieML(unittest.TestCase):
    def check_file(self, filename):
        with open(filename) as f:
            metadata = archieml.load(f)
            test = metadata['test']
            expected = json.loads(metadata['result'])

        with open(filename) as f:
            actual = archieml.load(f)
            del actual['test']
            del actual['result']

        self.assertEqual(expected, actual, (
            '{}\n'
            'expected: {}\n'
            'actual  : {}'
        ).format(test, expected, actual))

testdir = os.path.dirname(os.path.realpath(__file__))
files = glob.glob('{}/archieml.org/test/1.0/*.aml'.format(testdir))
files = filter(lambda f: 'all.0.aml' not in f and 'freeform' not in f, files)

for filename in files:
    slug, i = os.path.basename(filename).split('.')[:2]
    setattr(TestArchieML, 'test_{}_{}'.format(slug, i), lambda self: self.check_file(filename))
