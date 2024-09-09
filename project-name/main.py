from Atomic import Atomic
import argparse
import asyncio
from Executable import *
import glob
from mythic import mythic
import sys
import yaml

import time # TODO remove after testing

async def main():
    api_instance = None

    parser = argparse.ArgumentParser(description="Atomic testing through mythic")
    parser.add_argument('-u', '--username', type=str, help='username for the mythic user', required=True)
    parser.add_argument('-p', '--password', type=str, help='password for the mythic user', required=True)
    parser.add_argument('-H', '--hostname', type=str, help='hostname to run the tests on', required=True)
    parser.add_argument('-a', '--api', type=str, help='api to use for execution', default='mythic')
    parser.add_argument('-t ', '--timeout', type=int, help='timeout for each task to callback', default=300)
    parser.add_argument('-lf ', '--log-file', type=str, help='file to output logs', default='logs/logs.csv')
    parser.add_argument('-f ', '--atomic-file', type=str, help='run atomics from specific yaml file', default='./atomics/T*.yaml')
    parser.add_argument('-w', '--winget', help='check and install winget', default=False, const=True, nargs='?')
    args = parser.parse_args()

    callback_id = -1
    if args.api == "mythic":
        # Login and get setup callbacks:)
        api_instance = IMythic("C:\\temp\\ART", args.log_file, "C:\\Users\\domainadmin\\Desktop\\apollo.exe")
        await api_instance.login(args.username, args.password)
        await api_instance.get_parent_callback(args.hostname)
        await api_instance.get_child_callback(args.hostname, 0)
        await api_instance.update_all_callback_health()

    # Define the atomics objects
    for file in glob.glob(args.atomic_file):
        a = Atomic(file, api_instance, args.timeout, args.log_file, api_instance.parent_callback_id)

        if args.winget:
            pass
            # TODO this is now part of the api_instance
            # await a.tests[0].install_winget()

        # Atomic Tests
        for i, t in enumerate(a.tests):
            print(f"{i} -- {t.name}")
            if t.executor['name'] != "manual":
                err = await t.check_prereqs()
                if err is None:
                    await t.run_executor()
            await api_instance.manage_beacon_health(args.hostname)

if __name__ == "__main__":
    asyncio.run(main())
