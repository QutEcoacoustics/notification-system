import unittest
import datetime
from datetime import timedelta
from toad_functions import *
from dateutil import parser

class MyTest(unittest.TestCase):
    # There is one file in the folder, and the records indicate it has landed more than an hour after the
    # sensor that recorded it was last responsible for an automated mail
    # A notification should be sent
    scenario1_files = ["toad-2018-02-20-100000-sensor26.flac"]
    scenario1_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": false
    }"""
    scenario1_sensors = """{
      "sensor26": "2018-02-20 07:00:00.730124Z"
    }"""
    # There is one file in the folder, and the records indicate it has landed *less* than an hour after the
    # sensor that recorded it was last responsible for an automated mail
    # A notification should *NOT* be sent
    scenario2_files = ["toad-2018-02-20-100000-sensor26.flac"]
    scenario2_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": false
    }"""
    scenario2_sensors = """{
      "sensor26": "2018-02-20 09:30:00.730124Z"
    }"""
    # There are two unsent files in the folder, one of which is now clear of the trigger window
    # A notification should be sent containing both of them, and the trigger window reset to the present
    scenario3_files = ["toad-2018-02-20-100000-sensor26.flac", "toad-2018-02-20-110000-sensor26.flac"]
    scenario3_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": false,
      "toad-2018-02-20-110000-sensor26.flac": false
    }"""
    scenario3_sensors = """{
      "sensor26": "2018-02-20 09:30:00.730124Z"
    }"""
    # There are two unsent files and one sent file in the folder. One of the unsent files is from
    # a sensor that is currently on hold, but the other unsent file is from a sensor that hasn't
    # triggered since yesterday. Send a notification now with both of them.
    scenario4_files = ["toad-2018-02-20-100000-sensor26.flac",
                       "toad-2018-02-20-110000-sensor26.flac",
                       "toad-2018-02-20-110000-sensor28.flac"]
    scenario4_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": true,
      "toad-2018-02-20-110000-sensor26.flac": false,
      "toad-2018-02-20-110000-sensor28.flac": false
    }"""
    scenario4_sensors = """{
      "sensor26": "2018-02-20 10:10:00.730124Z",
      "sensor28": "2018-02-19 10:10:00.730124Z"
    }"""
    # There are a bunch of sent files and unsent files in the folder but none of the unsent files
    # are from sensors that haven't triggered in the past hour. *Don't* send anything yet.
    scenario5_files = ["toad-2018-02-18-100000-sensor26.flac",
                       "toad-2018-02-19-130042-sensor26.flac",
                       "toad-2018-02-20-100000-sensor28.flac",
                       "toad-2018-02-18-030000-sensor28.flac",
                       "toad-2018-02-20-110010-sensor26.flac",
                       "toad-2018-02-20-110010-sensor28.flac"]
    scenario5_file_history = """{
      "toad-2018-02-18-100000-sensor26.flac": true,
      "toad-2018-02-19-130042-sensor26.flac": true,
      "toad-2018-02-20-100000-sensor28.flac": true,
      "toad-2018-02-18-030000-sensor28.flac": true,
      "toad-2018-02-20-110010-sensor26.flac": false,
      "toad-2018-02-20-110010-sensor28.flac": false
    }"""
    scenario5_sensors = """{
      "sensor26": "2018-02-20 10:50:00.730124Z",
      "sensor28": "2018-02-20 10:50:00.730124Z"
    }"""

    def test_parseFileInfo(self):
      formats = [
        ["toad-2018-02-18-100000-sensor26.flac", "2018-02-18T10:00:00+0930", "sensor26"],
        ["toad-2018-02-18-100000+0930-sensor26.flac", "2018-02-18T10:00:00+0930", "sensor26"],
        ["toad-2018-02-18-100000Z-sensor26.flac", "2018-02-18T10:00:00Z", "sensor26"],
        ["toad-2018-02-18-100000-0930-sensor26.flac", "2018-02-18T10:00:00-0930", "sensor26"],

        ["toad-2018-03-20-012750-sensor26.flac", "2018-03-20T01:27:50+0930", "sensor26"],
        ["toad-2015-11-02-011755-sensor28.flac", "2015-11-02T01:17:55+0930", "sensor28"],
        ["toad-2010-11-20-011755-sensor99.flac", "2010-11-20T01:17:55+0930", "sensor99"],
      ]

      for test_case in formats:
        (filename, expected_date, expected_name) = test_case
        expected_date = parser.isoparse(expected_date)

        (actual_date, actual_name) = parseFileInfo(filename, timedelta(hours=9.5))
        self.assertEqual(expected_date, actual_date)
        self.assertEqual(expected_name, actual_name)

    def test_parseFileInfo_arg_validation(self):
        with self.assertRaises(TypeError):
            parseFileInfo("abc", None)

    def test_email_extraction(self):
        expected_result = ["test@example.com", "test2@ex.com"]
        test_result = getEmailsFromDropbox("<placeholder>", None, True, "test@example.com\ntest2@ex.com", ["<placeholder>"])
        self.assertEqual(test_result, expected_result)

    def test_scenario_1(self):
        files = self.scenario1_files
        file_history = json.loads(self.scenario1_file_history)
        sensor_history = json.loads(self.scenario1_sensors)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 1) # Notification should have been sent
        self.assertEqual(len(notifications_to_send), 1)
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 0)

    def test_scenario_2(self):
        files = self.scenario2_files
        file_history = json.loads(self.scenario2_file_history)
        sensor_history = json.loads(self.scenario2_sensors)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 1)
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well. Otherwise, it will be the same.
        (file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 1)

    def test_scenario_3(self):
        files = self.scenario3_files
        file_history = json.loads(self.scenario3_file_history)
        sensor_history = json.loads(self.scenario3_sensors)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 1) # Notification should have been sent
        self.assertEqual(len(notifications_to_send), 2)
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 0)

    def test_scenario_4(self):
        files = self.scenario4_files
        file_history = json.loads(self.scenario4_file_history)
        sensor_history = json.loads(self.scenario4_sensors)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 1) # Notification should have been sent
        self.assertEqual(len(notifications_to_send), 2)
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 0)

    def test_scenario_5(self):
        files = self.scenario5_files
        file_history = json.loads(self.scenario5_file_history)
        sensor_history = json.loads(self.scenario5_sensors)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 2)
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history) = updateState(notifications_to_send, activated_sensors, file_history, sensor_history)
        (notifications_to_send, activated_sensors) = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0))
        self.assertEqual(len(activated_sensors), 0)
        self.assertEqual(len(notifications_to_send), 2)

if __name__ == '__main__':
    unittest.main()