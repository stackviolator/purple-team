from Atomic import Atomic
import argparse
import asyncio
import configparser
from Executable import *
import glob
import sys
from utils import mythic_register_file as mregister_file
import warnings
import yaml

warnings.filterwarnings("ignore", message="Timeout reached in timeout_generator")


async def main():
    api_instance = None

    parser = argparse.ArgumentParser(description="Atomic testing through mythic")
    parser.add_argument(
        "-f", "--config-file", type=str, help="Config file for the API", required=True
    )
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config_file)
    api_config = config["api"]
    execution_config = config["execution"]
    payload_config = config["payloads"]

    # API Config
    username = api_config["Username"]
    password = api_config["Password"]
    domain = api_config["Domain"]
    hostname = api_config["Hostname"]
    api = api_config["API"]
    logfile = api_config["LogFile"]
    atomicfile = api_config["AtomicFile"]
    atomicpath = api_config["AtomicPath"]
    binarypath = api_config["BinaryPath"]
    timeout = int(api_config["Timeout"])
    install_winget = api_config.getboolean("InstallWinget")
    skip_health = api_config.getboolean("SkipHealth")

    # Execution config
    set_exec_config = execution_config.getboolean("SetConfig")

    callback_id = -1
    if api == "mythic":
        # Login and get setup callbacks:)
        api_token = mregister_file.auth(username, password)
        api_instance = IMythic(
            atomicpath, logfile, binarypath, execution_config, payload_config, api_token
        )
        await api_instance.login(username, password)
        await api_instance.get_parent_callback(hostname)
        try:
            await api_instance.get_child_callback(hostname, 0)
        except Exception as e:
            print("[-] Could not spawn child process")
            sys.exit(1)

        if set_exec_config:
            await api_instance.set_beacon_execution_config(
                api_instance.parent_callback_id
            )
            await api_instance.set_beacon_execution_config(
                api_instance.child_callback_id
            )

        if not skip_health:
            await api_instance.update_all_callback_health()

    # Define the atomics objects
    for file in glob.glob(atomicfile):
        a = Atomic(
            file, api_instance, timeout, logfile, api_instance.parent_callback_id
        )

        if install_winget:
            await api_instance.install_winget()
            
        # Atomic Tests
        for i, t in enumerate(a.tests):
            print(f"[*] Starting execution for task {t.name}")
            try:
                await t.run_atomic_test()
            except Exception as e:
                print(f"[-] Task failed with exception -- '{e}'")
                print(f"[-] Skipping task '{t.name}'...")
                print("")
                continue
            if not skip_health:
                try:
                    await api_instance.manage_beacon_health(hostname)
                except Exception as e:
                    # Can prob put this into Executable.py
                    if e == "Parent beacon died":
                        for i in range(5):
                            print(
                                f"[+] Dead parent beacon found, waiting {timeout} then trying again..."
                            )
                            try:
                                health = api_instance.check_beacon_health(
                                    api_instance.parent_callback_id
                                )
                                if health == "Alive":
                                    break
                            except Exception as e:
                                pass
            print("")  # Space out the output per test


if __name__ == "__main__":
    asyncio.run(main())
