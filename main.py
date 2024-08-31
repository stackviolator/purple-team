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
    # Login :)
    mythic_instance = await login()

    # Define atomics object
    a = Atomic("atomics/T1003.001.yaml", "mythic", mythic_instance, 20)

    # Atomic Tests
    p_test = a.tests[0]
    await p_test.check_prereqs()
    await p_test.run_executor()

    p_test = a.tests[1]
    await p_test.check_prereqs()
    await p_test.run_executor()

    p_test = a.tests[2]
    await p_test.check_prereqs()
    await p_test.run_executor()

if __name__ == "__main__":
    asyncio.run(main())
