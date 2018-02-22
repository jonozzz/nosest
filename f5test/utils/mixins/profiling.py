from collections import defaultdict
import csv
import os
import time

from enum import Enum


class BasicProfilerState(Enum):
    disabled = 1
    enabled = 2
    dont_save = 3


class BasicProfiler(object):
    results = []
    current_test = None
    state = BasicProfilerState.disabled

    @classmethod
    def set_test_name(cls, name):
        cls.current_test = str(name)

    @classmethod
    def save_result(cls, key, **kwargs):
        cls.results.append({'test' : cls.current_test,
                'req_type' : kwargs['req_type'],
                'start_time' : kwargs['start_time'],
                'end_time' : kwargs['end_time'],
                'url' : key
                })

    @classmethod
    def output_result_to_file(cls, session_path, out_file, baseline=None):
        # Load baseline file for performance information
        data = defaultdict(list)
        if baseline and os.path.isfile(baseline):
            with open(baseline) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data[row['Test']].append([row['Endpoint'],
                                            row['Method'],
                                            row['Start Time'],
                                            row['End Time'],
                                            row['Total Time (sec)']])

        # Write csv file with new results and comparision with baseline
        if os.path.exists(session_path) and BasicProfiler.results:
            with open(os.path.join(session_path, out_file), 'wb') as f:
                csvwriter = csv.writer(f)
                count = 0
                prev_test_name = None
                header = []
                header.append('Test')
                header.append('Endpoint')
                header.append('Method')
                header.append('Start Time')
                header.append('End Time')
                header.append('Total Time (sec)')
                if data:
                    header.append('Baseline Endpoint')
                    header.append('Baseline Method')
                    header.append('Baseline Total Time')
                    header.append('Degrade')
                csvwriter.writerow(header)
                for res in cls.results:
                    row = []
                    test_name = res['test']
                    if test_name and test_name != prev_test_name:
                        count = 0

                    row.append(test_name)
                    if res['url'].startswith("https://localhost"):
                        row.append(res['url'][len("https://localhost"):])
                    else:
                        row.append(res['url'])
                    row.append(res['req_type'])
                    row.append(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(res['start_time'])))
                    row.append(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(res['end_time'])))
                    total_time = res['end_time'] - res['start_time']
                    row.append(total_time)

                    if data and data[test_name] and count < len(data[test_name]):
                        row.append(data[test_name][count][0])
                        row.append(data[test_name][count][1])
                        row.append(data[test_name][count][4])
                        if total_time > 1 and total_time > float(data[test_name][count][4]) * 1.2:
                            row.append("X")
                        count += 1

                    csvwriter.writerow(row)
                    prev_test_name = test_name

        del cls.results[:]
        cls.currentTest = None
