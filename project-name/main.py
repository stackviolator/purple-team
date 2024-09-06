from Atomic import Atomic
import argparse
import asyncio
import glob
from mythic import mythic
import sys
import yaml

async def login(username, password):
    return await mythic.login(
            username=username,
            password=password,
            server_ip="localhost",
            server_port=7443,
            timeout=-1
        )

# Update callback info, could be useful but was using as a POC
async def update_callback(mythic_instance):
    await mythic.update_callback(
        mythic=mythic_instance,
        callback_display_id=7,
        description="Updated from API",
        locked=True,
        domain="ludus.local",
        integrity_level=3,
        host="lab-dc",
        user="domainadmin"
    )

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

    """ SETUP """
    callback_id = -1
    if args.api == "mythic":
        # Login :)
        api_instance = await login(args.username, args.password)

        # Get the callback ID
        callbacks = await mythic.get_all_active_callbacks(mythic=api_instance)
        for c in callbacks:
            if c['host'] == args.hostname:
                callback_id = c['display_id']
        if callback_id == -1:
            print(f'[-] Failed to get callback on host: {args.hostname}')
            sys.exit(-1)

    # Check if the API Instance exists
    if api_instance is None:
        print(f'[-] API ({args.api}) Instance is None')
        sys.exit(-1)

    # Define the atomics objects
    for file in glob.glob(args.atomic_file):
        a = Atomic(file, args.api, api_instance, args.timeout, args.log_file, callback_id)

        if args.winget:
            await a.tests[0].install_winget()
        """ SETUP """

        # Atomic Tests
        for i, t in enumerate(a.tests):
            print(f"{i} -- {t.name}")
            if t.executor['name'] != "manual":
                err = await t.check_prereqs()
                if err is None:
                    await t.run_executor()

if __name__ == "__main__":
    asyncio.run(main())
