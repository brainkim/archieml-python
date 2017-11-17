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
        ).format(test, expected, json.loads(json.dumps(actual))))

testdir = os.path.dirname(os.path.realpath(__file__))
files = glob.glob(testdir + '/archieml.org/test/1.0/*.aml')
# https://github.com/newsdev/archieml.org/issues/36
files = [f for f in files if 'multi_line.16.aml' not in f]
files = [f for f in files if 'all.0.aml' not in f]
files = files + glob.glob(testdir + '/custom/*.aml')

for filename in files:
    slug, i = os.path.basename(filename).split('.')[:2]
    def check_file(filename):
        return lambda self: self.check_file(filename)
    setattr(TestArchieML, 'test_{}_{}'.format(slug, i), check_file(filename))
