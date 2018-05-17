import unittest
import datetime
from toad_functions import *

class MyTest(unittest.TestCase):
    # There is one file in the folder, and the records indicate it has landed more than an hour after the
    # sensor that recorded it was last responsible for an automated mail
    # A notification should be sent
    scenario1_files = """{
      "toad-2018-02-20-100000-sensor26.flac": false
    }"""
    scenario1_sensors = """{
      "sensor26": "2018-02-20 07:00:00.730124"
    }"""
    # There is one file in the folder, and the records indicate it has landed *less* than an hour after the
    # sensor that recorded it was last responsible for an automated mail
    # A notification should *NOT* be sent
    scenario2_files = """{
      "toad-2018-02-20-100000-sensor26.flac": false
    }"""
    scenario2_sensors = """{
      "sensor26": "2018-02-20 09:30:00.730124"
    }"""
    # There are two unsent files in the folder, one of which is now clear of the trigger window
    # A notification should be sent containing both of them, and the trigger window reset to the present
    scenario3_files = """{
      "toad-2018-02-20-100000-sensor26.flac": false,
      "toad-2018-02-20-110000-sensor26.flac": false
    }"""
    scenario3_sensors = """{
      "sensor26": "2018-02-20 09:30:00.730124"
    }"""
    # There are two unsent files and one sent file in the folder. One of the unsent files is from
    # a sensor that is currently on hold, but the other unsent file is from a sensor that hasn't
    # triggered since yesterday. Send a notification now with both of them.
    scenario4_files = """{
      "toad-2018-02-20-100000-sensor26.flac": true,
      "toad-2018-02-20-110000-sensor26.flac": false,
      "toad-2018-02-20-110000-sensor28.flac": false
    }"""
    scenario4_sensors = """{
      "sensor26": "2018-02-20 10:10:00.730124",
      "sensor28": "2018-02-19 10:10:00.730124"
    }"""
    # There are a bunch of sent files and unsent files in the folder but none of the unsent files
    # are from sensors that haven't triggered in the past hour. *Don't* send anything yet.
    scenario5_files = """{
      "toad-2018-02-18-100000-sensor26.flac": true,
      "toad-2018-02-19-130042-sensor26.flac": true,
      "toad-2018-02-20-100000-sensor28.flac": true,
      "toad-2018-02-18-030000-sensor28.flac": true,
      "toad-2018-02-20-110010-sensor26.flac": false,
      "toad-2018-02-20-110010-sensor28.flac": false
    }"""
    scenario5_sensors = """{
      "sensor26": "2018-02-20 10:50:00.730124",
      "sensor28": "2018-02-20 10:50:00.730124"
    }"""


    def test_sensor_data(self):
        test_string = "toad-2018-03-20-012750-sensor26.flac"
        expected_result = (datetime(2018, 3, 20, 1, 27, 50), 'sensor26')
        self.assertEqual(parseFileInfo(test_string), expected_result)
        test_string = "toad-2015-11-02-011755-sensor28.flac"
        expected_result = (datetime(2015, 11, 2, 1, 17, 55), 'sensor28')
        self.assertEqual(parseFileInfo(test_string), expected_result)
        test_string = "toad-2010-11-20-011755-sensor99.flac"
        expected_result = (datetime(2010, 11, 20, 1, 17, 55), 'sensor99')
        self.assertEqual(parseFileInfo(test_string), expected_result)

    def test_email_extraction(self):
        expected_result = ["test@example.com", "test2@ex.com"]
        test_result = getEmailsFromDropbox(None, "<placeholder>", None, True, "test@example.com\ntest2@ex.com", ["<placeholder>"])
        self.assertEqual(test_result, expected_result)

    def test_scenario_1(self):
        file_history = json.loads(self.scenario1_files)
        sensor_history = json.loads(self.scenario1_sensors)
        files = ['toad-2018-02-20-100000-sensor26.flac']
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600)
        print(notifications_to_send)
        print(activated_sensors)
        self.assertEqual(len(activated_sensors) == 1, True)
        self.assertEqual(len(notifications_to_send) == 1, True)

if __name__ == '__main__':
    unittest.main()