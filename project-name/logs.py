import csv
import os
import sys


class Logger:
    def __init__(self, filepath):
        self.filepath = filepath
        self.fieldnames = [
            "command",
            "timestamp",
            "status",
            "api",
            "name",
            "GUID",
            "description",
            "platform",
            "executor",
            "timeout",
            "callback_id",
            "output",
        ]

    """
    Fields: command, time, status, api, name, GUID, Description, platform, executor, timeout, callback_id, output
    """

    def log(self, data):
        # Test if file exists
        file_exists = os.path.isfile(self.filepath)
        # Open file in write mode if it doesn't exist, otherwise in append mode
        mode = "a" if file_exists else "w"
        try:
            with open(self.filepath, mode, newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                # Write header if the file was just created
                if not file_exists:
                    writer.writeheader()
                writer.writerows(data)

        except IOError:
            print(f"[-] Could not open {self.filepath} for logging")
            sys.exit(1)
