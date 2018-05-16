import unittest
import datetime
from toad_functions import *

class MyTest(unittest.TestCase):
    def test(self):
        test_string = "toad-2018-03-20-012750-sensor26.flac"
        expected_result = (datetime(2018, 3, 20, 1, 27, 50), 'sensor26')
        self.assertEqual(parseFileInfo(test_string), expected_result)
        test_string = "toad-2015-11-02-011755-sensor28.flac"
        expected_result = (datetime(2015, 11, 2, 1, 17, 55), 'sensor28')
        self.assertEqual(parseFileInfo(test_string), expected_result)
        test_string = "toad-2010-11-20-011755-sensor99.flac"
        expected_result = (datetime(2010, 11, 20, 1, 17, 55), 'sensor99')
        self.assertEqual(parseFileInfo(test_string), expected_result)

if __name__ == '__main__':
    unittest.main()