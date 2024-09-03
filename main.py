from Atomic import Atomic
import argparse
import asyncio
from mythic import mythic
import sys
import yaml

async def login():
    return await mythic.login(
            username="mythic_admin",
            password=sys.argv[1],
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
    # TODO, take these in as a cli params
    API = "mythic"
    api_instance = None
    HOSTNAME = "GORILLA-DC01-2022"
    TIMEOUT = 60

    """ SETUP """
    callback_id = -1
    if API == "mythic":
        # Login :)
        api_instance = await login()

        # Get the callback ID
        callbacks = await mythic.get_all_active_callbacks(mythic=api_instance)
        for c in callbacks:
            if c['host'] == HOSTNAME:
                callback_id = c['display_id']
        if callback_id == -1:
            print(f'[-] Failed to get callback on host: {HOSTNAME}')
            sys.exit(-1)

    # Check if the API Instance exists
    if api_instance is None:
        print(f'[-] API ({API}) Instance is None')
        sys.exit(-1)

    # Define atomics object
    a = Atomic("atomics/T1003.001.yaml", API, api_instance, TIMEOUT, callback_id)
    # TODO uncomment later :) # await a.tests[0].install_winget()
    """ SETUP """

    """ TESTING """
    # Atomic Tests
    if sys.argv[-1] == '-t':
        for i, t in enumerate(a.tests):
            print(f"{i} -- {t.name}")
            if t.executor['name'] != "manual":
                err = await t.check_prereqs()
                if err is None:
                    await t.run_executor()
    """ TESTING """

if __name__ == "__main__":
    asyncio.run(main())
