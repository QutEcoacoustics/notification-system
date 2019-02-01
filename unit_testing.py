import unittest
import json
import datetime
from datetime import timedelta
from datetime import timezone
from toad_functions import (
  getEmailsFromDropbox, 
  getNotificationsAndActivatingSensors,
  updateState,
  parseFileInfo,
  SensorState, 
  formatNotifications,
  filterSensorDirs,
  filterGroupLogFiles,
  closeToTimeOfDay,
  parse_whitelist_times,
  time_ranges_contain_time_from_date
)
from dateutil import parser
import re

class FileMetadataMock():
    MOCK_ROOT =  "/mock_path/"

    def __init__(self, name):
        if isinstance(name, dict):
            self._path_lower = name["path_lower"]
            self._name = name["name"]
        else:
            self._path_lower = self.MOCK_ROOT + name
            self._name = name

    @property
    def name(self): return self._name

    @property
    def path_lower(self): return self._path_lower
  
    @staticmethod
    def make_files(filenames):
      return [ FileMetadataMock(x) for x in filenames ]


class MyTest(unittest.TestCase):
    default_time_whitelist = parse_whitelist_times(None)

    # There is one file in the folder, and the records indicate it has landed more than an hour after the
    # sensor that recorded it was last responsible for an automated mail
    # A notification should be sent
    scenario1_files = FileMetadataMock.make_files(["toad-2018-02-20-100000-sensor26.flac"])
    scenario1_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": false
    }"""
    scenario1_sensors = """{
      "sensor26": "2018-02-20 07:00:00.730124Z"
    }"""
    scenario1_now = "2018-02-20 10:00:00.000000Z"
    # There is one file in the folder, and the records indicate it has landed *less* than an hour after the
    # sensor that recorded it was last responsible for an automated mail
    # A notification should *NOT* be sent
    scenario2_files = FileMetadataMock.make_files(["toad-2018-02-20-100000-sensor26.flac"])
    scenario2_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": false
    }"""
    scenario2_sensors = """{
      "sensor26": "2018-02-20 09:30:00.730124Z"
    }"""
    scenario2_now = "2018-02-20 10:05:00.000000Z"
    # There are two unsent files in the folder, one of which is now clear of the trigger window
    # A notification should be sent containing both of them, and the trigger window reset to the present
    scenario3_files = FileMetadataMock.make_files(["toad-2018-02-20-100000-sensor26.flac", "toad-2018-02-20-110000-sensor26.flac"])
    scenario3_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": false,
      "toad-2018-02-20-110000-sensor26.flac": false
    }"""
    scenario3_sensors = """{
      "sensor26": "2018-02-20 09:30:00.730124Z"
    }"""
    scenario3_now = "2018-02-20 11:00:00.000000Z"
    # There are two unsent files and one sent file in the folder. One of the unsent files is from
    # a sensor that is currently on hold, but the other unsent file is from a sensor that hasn't
    # triggered since yesterday. Send a notification now with both of them.
    scenario4_files = FileMetadataMock.make_files(["toad-2018-02-20-100000-sensor26.flac",
                       "toad-2018-02-20-110000-sensor26.flac",
                       "toad-2018-02-20-110000-sensor28.flac"])
    scenario4_file_history = """{
      "toad-2018-02-20-100000-sensor26.flac": true,
      "toad-2018-02-20-110000-sensor26.flac": false,
      "toad-2018-02-20-110000-sensor28.flac": false
    }"""
    scenario4_sensors = """{
      "sensor26": "2018-02-20 10:00:00.730124Z",
      "sensor28": "2018-02-19 10:10:00.730124Z"
    }"""
    scenario4_now = "2018-02-20 11:00:00.000000Z"
    # There are a bunch of sent files and unsent files in the folder but none of the unsent files
    # are from sensors that haven't triggered in the past hour. *Don't* send anything yet.
    scenario5_files = FileMetadataMock.make_files(["toad-2018-02-18-100000-sensor26.flac",
                       "toad-2018-02-19-130042-sensor26.flac",
                       "toad-2018-02-20-100000-sensor28.flac",
                       "toad-2018-02-18-030000-sensor28.flac",
                       "toad-2018-02-20-110010-sensor26.flac",
                       "toad-2018-02-20-110010-sensor28.flac"])
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
    scenario5_now = "2018-02-20 11:10:00.000000Z"

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
        now =  parser.isoparse(self.scenario1_now)
        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 1, 1, 1)
        
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history, send_notifications) = updateState(*actual, file_history, sensor_history, now)
        self.assertEqual(send_notifications, True)

        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 1, 0, 0)

    def test_scenario_2(self):
        files = self.scenario2_files
        file_history = json.loads(self.scenario2_file_history)
        sensor_history = json.loads(self.scenario2_sensors)
        now = parser.isoparse(self.scenario2_now)
        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 1, 0, 1)
        
        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well. Otherwise, it will be the same.
        (file_history, sensor_history, send_notifications) = updateState(*actual, file_history, sensor_history, now)
        self.assertEqual(send_notifications, False)

        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 1, 0, 1)

    def test_scenario_3(self):
        files = self.scenario3_files
        file_history = json.loads(self.scenario3_file_history)
        sensor_history = json.loads(self.scenario3_sensors)
        now = parser.isoparse(self.scenario3_now)
        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 1, 1, 2)

        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history, send_notifications) = updateState(*actual, file_history, sensor_history, now)
        self.assertEqual(send_notifications, True)

        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 1, 0, 0)

    def test_scenario_4(self):
        files = self.scenario4_files
        file_history = json.loads(self.scenario4_file_history)
        sensor_history = json.loads(self.scenario4_sensors)
        now = parser.isoparse(self.scenario4_now)
        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 2, 1, 2)

        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history, send_notifications) = updateState(*actual, file_history, sensor_history, now)
        self.assertEqual(send_notifications, True)

        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 2, 0, 0)

    def test_scenario_5(self):
        files = self.scenario5_files
        file_history = json.loads(self.scenario5_file_history)
        sensor_history = json.loads(self.scenario5_sensors)
        now = parser.isoparse(self.scenario5_now)
        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 2, 0, 2)

        # Test state update. This should always result in zero activated sensors, and if a notification *was* sent,
        # the count of notifications to send should now be zero as well.
        (file_history, sensor_history, send_notifications) = updateState(*actual, file_history, sensor_history, now)
        self.assertEqual(send_notifications, False)

        actual = getNotificationsAndActivatingSensors(files, file_history, sensor_history, 3600, timedelta(hours=0), now, self.default_time_whitelist)
        self.assert_notifications(actual, 2, 0, 2)
        
    def test_flush_events(self):
      # pending notifications should be flushed immediately after the timeout
      # pseudo simulates are 5-minute checker
      #  "toad-2018-08-12-190631-sensor36.flac", # trigger
      #  "toad-2018-08-12-194235-sensor36.flac", # suppress
      #  "toad-2018-08-12-200636-sensor36.flac", # trigger (include both events)
      #  "toad-2018-08-14-074924-sensor36.flac", # trigger

      f1 = "toad-2018-08-12-190631-sensor36.flac"
      f2 = "toad-2018-08-12-194235-sensor36.flac"
      f3 = "toad-2018-08-12-200636-sensor36.flac"
      f4 = "toad-2018-08-14-074924-sensor36.flac"
      trigger_times = [
        {"date": "2018-08-12T19:10:00+10:00", "activated": 1, "notifications": 1, "send_notifications": True, "new_files": [f1], "expected_history": {f1: True}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-12T19:45:00+10:00", "activated": 0, "notifications": 1, "send_notifications": False, "new_files": [f2], "expected_history": {f1: True, f2: False}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-12T20:10:00+10:00", "activated": 1, "notifications": 2, "send_notifications": True, "new_files": [f3], "expected_history": {f1: True, f2: True, f3: True}, "sensor_last_update": "2018-08-12T20:10:00+10:00"},
        {"date": "2018-08-14T07:50:00+10:00", "activated": 1, "notifications": 1, "send_notifications": True, "new_files": [f4], "expected_history": {f1: True, f2: True, f3: True, f4: True}, "sensor_last_update": "2018-08-14T07:50:00+10:00"},
      ] 

      self.step_runner(trigger_times)    
        
    def test_flush_events_no_trigger(self):
      # pending notifications should be flushed immediately after the timeout
      # rather whenever the next event is triggered, even when there are no events
      # pseudo-simulates a 5-minute checker
      #  "toad-2018-08-12-190631-sensor36.flac", # trigger
      #  "toad-2018-08-12-194235-sensor36.flac", # suppress
      #  "toad-2018-08-12-200236-sensor36.flac", # suppress
      #  # another run, without a file trigger, at 20:10 "flushes" the cache
      #  "toad-2018-08-14-074924-sensor36.flac", # trigger

      f1 = "toad-2018-08-12-190631-sensor36.flac"
      f2 = "toad-2018-08-12-194235-sensor36.flac"
      f3 = "toad-2018-08-12-200236-sensor36.flac"
      f4 = "toad-2018-08-14-074924-sensor36.flac"
      trigger_times = [
        {"date": "2018-08-12T19:10:00+10:00", "activated": 1, "notifications": 1, "send_notifications": True, "new_files": [f1], "expected_history": {f1: True}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-12T19:45:00+10:00", "activated": 0, "notifications": 1, "send_notifications": False,"new_files": [f2], "expected_history": {f1: True, f2: False}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-12T20:05:00+10:00", "activated": 0, "notifications": 2, "send_notifications": False,"new_files": [f3], "expected_history": {f1: True, f2: False, f3: False}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-12T20:10:00+10:00", "activated": 1, "notifications": 2, "send_notifications": True, "new_files": [], "expected_history": {f1: True, f2: True, f3: True}, "sensor_last_update": "2018-08-12T20:10:00+10:00"},
        {"date": "2018-08-14T07:50:00+10:00", "activated": 1, "notifications": 1, "send_notifications": True, "new_files": [f4], "expected_history": {f1: True, f2: True, f3: True, f4: True}, "sensor_last_update": "2018-08-14T07:50:00+10:00"},
      ]

      self.step_runner(trigger_times)
        
    def test_sensors_should_not_activate_with_no_files(self):
      # sensors should not activate for no reason

      trigger_times = [
        {"date": "2018-08-12T19:10:00+10:00", "activated": 0, "notifications": 0, "send_notifications": False, "new_files": [], "expected_history": {}, "sensor_last_update": "2018-08-12T18:00:00+10:00"},
        {"date": "2018-08-12T20:10:00+10:00", "activated": 0, "notifications": 0, "send_notifications": False,"new_files": [], "expected_history": {}, "sensor_last_update": "2018-08-12T18:00:00+10:00"},
      ]

      self.step_runner(trigger_times)

            
    def test_whitelist_times_should_be_respected(self):
      # files that do not occur in whitelist should be never reported

      f1 = "toad-2018-08-12-190631-sensor36.flac"
      f2 = "toad-2018-08-13-120000-sensor36.flac"
      f3 = "toad-2018-08-13-200236-sensor36.flac"

      trigger_times = [
        {"date": "2018-08-12T19:10:00+10:00", "activated": 1, "notifications": 1, "send_notifications": True, "new_files": [f1], "expected_history": {f1: True}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-13T12:05:00+10:00", "activated": 0, "notifications": 1, "send_notifications": False,"new_files": [f2], "expected_history": {f1: True, f2: None}, "sensor_last_update": "2018-08-12T19:10:00+10:00"},
        {"date": "2018-08-13T20:10:00+10:00", "activated": 1, "notifications": 1, "send_notifications": True,"new_files": [f3], "expected_history": {f1: True, f2: None, f3: True}, "sensor_last_update": "2018-08-13T20:10:00+10:00"},
      ]

      self.step_runner(trigger_times)

    def test_filter_sensor_dirs(self):
        test_files = FileMetadataMock.make_files([
            "toads",
            "sensor7",
            "sensor8",
            "sensor9",
            "toad",
            "sensor0",
            "email_alert_list.txt",
            "script-orig.sh",
            "sw-update-v10.sh",
            "v10.tar",
            "sw-update-v10-debug.sh",
            "script.sh"])

        actual = list(filterSensorDirs(test_files, FileMetadataMock.MOCK_ROOT + "toads"))

        expected = [
            (FileMetadataMock.MOCK_ROOT + "sensor7/logs", "sensor7"),
            (FileMetadataMock.MOCK_ROOT + "sensor8/logs", "sensor8"),
            (FileMetadataMock.MOCK_ROOT + "sensor9/logs", "sensor9"),
            (FileMetadataMock.MOCK_ROOT + "sensor0/logs", "sensor0")]
        self.assertEqual(actual, expected)

    def test_group_log_files(self):
        with open("test/fixtures/log_listing.json") as f:
            log_listing = FileMetadataMock.make_files(json.load(f)["entries"])

        tz = timezone(timedelta(hours=10))
        report_date = datetime.datetime(2018, 8, 28, 12, 0, tzinfo=tz)
        limit = timedelta(days=3)
        fallback_utc_offset = timedelta(hours=10)

        # test limitless reporting
        actual = filterGroupLogFiles(log_listing, report_date, None, fallback_utc_offset)
        self.assertEqual(len(actual), 76)

        # limit to last n days
        actual = filterGroupLogFiles(log_listing, report_date, limit, fallback_utc_offset)

        # its just before the report date of 12:01, so -3days will include 3 previous
        # reports, and +3days will include today and 2 future reports
        self.assertEqual(len(actual), 6)
        expected_dates = list(map(lambda i:  datetime.date(2018, 8, i).isoformat(), range(25, 31)))
        self.assertCountEqual(actual.keys(), expected_dates)
        
        expected_reports = zip(expected_dates, [4, 1, 6, 1, 1, 1], [1, 1, 1, 1, 1, 1])
        for (day, up_count, down_count) in expected_reports:
            log_entries = actual[day]
            # one up, one down, entry for each day (when there isn't a fault with the sensor!)
            self.assertEqual(len(log_entries), up_count + down_count)
            self.assertEqual(len(list(filter(lambda entry: entry[2] == "up", log_entries))), up_count)
            self.assertEqual(len(list(filter(lambda entry: entry[2] == "down", log_entries))), down_count)

    def test_close_to_time_of_day(self):
      times = ["12:00", "15:00"]

      test_cases = [
        ("2018-08-12T15:00:00", True),
        ("2018-08-12T15:05:00", False),
        ("2018-08-12T15:04:00", True),
        ("2018-08-12T14:00:00", False),
        ("2018-08-12T14:55:00", False),
        ("2018-08-12T14:55:01", False),
        ("2018-08-12T15:00:00+10:00", True),
        ("2018-08-12T15:05:00+10:00", False),
        ("2018-08-12T15:04:00+10:00", True),
        ("2018-08-12T14:00:00+10:00", False),
        ("2018-08-12T14:55:00+10:00", False),
        ("2018-08-12T14:55:01+10:00", False),
      ]

      for (test_now_string, expected) in test_cases:
        test_now = parser.parse(test_now_string)
        self.assertEqual(closeToTimeOfDay(test_now, times), expected)

    def test_parse_whitelist_times(self):
        test_cases = [
            None,
            [],
            [["00:00", "24:00"]],
            [["20:00", "24:00"], ["00:00", "05:30"]],
        ]

        expected = [
            [(timedelta(days=0), timedelta(days=1))],
            [(timedelta(days=0), timedelta(days=1))],
            [(timedelta(days=0), timedelta(days=1))],
            [(timedelta(hours=20), timedelta(days=1)), ((timedelta(days=0), timedelta(hours=5, minutes=30)))],
        ]

        for (input, expected) in zip(test_cases, expected):
            actual = parse_whitelist_times(input)
            self.assertEqual(expected, actual, f"test case: {input}")

    def test_time_ranges_contain_time_from_date(self):
        test_cases_whitelist = [
            [(timedelta(days=0), timedelta(days=1))],
            [(timedelta(days=0), timedelta(days=1))],
            [(timedelta(days=0), timedelta(days=1))],
            [(timedelta(hours=20), timedelta(days=1)), (timedelta(days=0), timedelta(hours=5, minutes=30))],
            [(timedelta(hours=20), timedelta(days=1)), (timedelta(days=0), timedelta(hours=5, minutes=30))],
            [(timedelta(hours=20), timedelta(days=1)), (timedelta(days=0), timedelta(hours=5, minutes=30))],
            [(timedelta(hours=20), timedelta(days=1)), (timedelta(days=0), timedelta(hours=5, minutes=30))],
            [(timedelta(hours=20), timedelta(days=1)), (timedelta(days=0), timedelta(hours=5, minutes=30))],
        ]

        test_cases_dates = [
            ("2018-08-12T14:55:01", True),
            ("2018-08-12T23:59:59", True),
            ("2018-08-12T00:00:00", True),
            ("2018-08-12T14:55:01", False),
            ("2018-08-12T20:00:00", True),
            ("2018-08-12T00:00:00", True),
            ("2018-08-12T05:30:00", False),
            ("2018-08-12T12:00:00", False),
        ]

        for (whitelist, (date, expected)) in zip(test_cases_whitelist, test_cases_dates):
            date = parser.parse(date)
            actual = time_ranges_contain_time_from_date(whitelist, date)
            self.assertEqual(expected, actual, f"failed for `{date}`")

    #
    # Helper methods
    #

    def assert_notifications(self, actual, sensor_count, sensor_active, notification_count):
        (notifications_to_send, sensors_status) = actual
        self.assertEqual(len(sensors_status), sensor_count)
        self.assertEqual(sum(v == SensorState.ACTIVATED for (k,v) in sensors_status.items()), sensor_active)
        self.assertEqual(len(notifications_to_send), notification_count)

    def step_runner(self, steps):
      db_files = []
      file_history = {}
      sensor_history = {"sensor36": "2018-08-12T18:00:00+10:00"}
      times_whitelist =  [
          (timedelta(hours=18), timedelta(days=1)), 
          (timedelta(days=0), timedelta(hours=10))
          ]
      for step in steps:
        now = parser.isoparse(step["date"])

        print(f"running step for time {now}")

        db_files = db_files + FileMetadataMock.make_files(step["new_files"])
        expected_history = step["expected_history"]
        sensor_last_update = step["sensor_last_update"]

        actual = getNotificationsAndActivatingSensors(db_files, file_history, sensor_history, 3600, timedelta(hours=10), now, times_whitelist)
        self.assert_notifications(actual, 1, step["activated"], step["notifications"])

        (file_history, sensor_history, send_notifications) = updateState(*actual, file_history, sensor_history, now)
                
        self.assertEqual(file_history, expected_history)
        self.assertEqual(sensor_history, {"sensor36": sensor_last_update})
        self.assertEqual(send_notifications, step["send_notifications"])

        body = formatNotifications(*actual, lambda path: "fakeurl://" + path)

        self.assertEqual(len(re.findall("sensor36</h2>", body)), 1 if send_notifications else 0)
        if send_notifications:
            notifications_to_send = actual[0]
            for (entry, *_) in notifications_to_send:
                self.assertRegex(body, "fakeurl:///mock_path/" + entry.name)


if __name__ == '__main__':
    unittest.main()