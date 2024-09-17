import argparse
from Command import Command
import logs
from mythic import mythic
import os
import re
import sys
import yaml

DISALLOWED_EXECUTORS = ['manual']

class Atomic:
    def __init__(self, file, api_instance, timeout, logfile, callback_id=None):
        self.api_instance = api_instance
        self.file = file
        self.timeout = timeout
        self.callback_id = callback_id
        self.logfile = logfile

        self.parse_yaml()

    def load_atomic_yaml(self):
        with open(self.file, 'r') as file:
            self.yaml = yaml.safe_load(file)

    def parse_yaml(self):
        self.load_atomic_yaml()

        self.attack_technique = self.yaml['attack_technique']
        self.display_name = self.yaml['display_name']
        self.tests = [AtomicTest(dict(x), self.api_instance, self.timeout, self.callback_id) for x in self.yaml['atomic_tests']] # sick list comprehension

class AtomicTest:
    def __init__(self, test, api_instance, timeout, logfile, callback_id=None):
        self.api_instance = api_instance
        self.name = test['name']
        self.guid = test['auto_generated_guid']
        self.description = test['description']
        self.platforms = test['supported_platforms']
        self.args = test.get('input_arguments', {})
        self.dependency_executor = test.get('dependency_executor_name', 'powershell')
        self.dependencies = test.get('dependencies', {})
        self.executor = test.get('executor', {})
        self.elevation_required = self.executor.get('elevation_required',  False)
        self.timeout = timeout
        self.callback_id = callback_id

    # Check the command to be run in the TTP to see if the binary is in the whitelist
    async def run_atomic_test(self):
        cmd = Command(self.executor["name"], self.executor["command"], self.name, self.guid, self.description, self.platforms, self.timeout, self.args)

        # Run preprocessing
        self.api_instance.clean_cmd(cmd)
        special_exec, method = self.api_instance.check_special_execution(cmd)

        try:
            await self.check_prereqs(special_exec, method)
            await self.run_executor(special_exec, method)

        except Exception as e:
            raise e

    # Checks the prereqs, returns an error
    async def check_prereqs(self, special_exec, method):
        # Check if elevation is required
        has_elevation = await self.api_instance.check_elevation(self.elevation_required)
        if not has_elevation:
            # Print warning, log the event, then skip then raise an exception
            err_str = f"FAILED: Test {self.name} requires elevation but child beacon is not running in high integrity"
            self.api_instance.log_error(self.name, self.guid, self.description, self.platforms, self.timeout, self.api_instance.child_callback_id, err_str)
            raise Exception(f"Elevation requirements not met for task {self.name}")

        # Check supported platforms
        valid_platform = await self.api_instance.check_platforms(self.platforms)
        if not valid_platform:
            # Print warning, log the event, then skip then raise an exception
            err_str = f"FAILED: Test {self.name} beacon OS is not in {self.platforms}"
            self.api_instance.log_error(self.name, self.guid, self.description, self.platforms, self.timeout, self.api_instance.child_callback_id, err_str)
            raise Exception(f"Platform requirements not met for task {self.name}")

        # Check Executor name
        if self.executor['name'].lower() in DISALLOWED_EXECUTORS:
            # Print warning, log the event, then skip then raise an exception
            err_str = f"FAILED: Test {self.name} has unsupported executor {self.executor['name']}"
            self.api_instance.log_error(self.name, self.guid, self.description, self.platforms, self.timeout, self.api_instance.child_callback_id, err_str)
            raise Exception(f"Unsupported executor \"{self.executor['name']}\" for task {self.name}")
        
        if special_exec:
            binpath = ''
            cmd = Command(self.executor["name"], self.executor["command"], self.name, self.guid, self.description, self.platforms, self.timeout, self.args)
            self.api_instance.clean_cmd(cmd)

            # execute_pe method
            if method == 'pe':
                # Check if the file is on disk
                name = re.findall(r'\b\w+\.exe\b', cmd.parameters)[0] # Regex to find <name>.exe
                for root, dirs, files in os.walk('payloads'):
                    if name in files:
                        binpath = os.path.join(root,name)
                # Alter download file check
                if binpath == '':
                    print("TODO: ADD LOGIC TO DOWNLOAD THE FILE")
                    sys.exit(0)
                # Register file
                await self.api_instance.register_file(binpath, self.api_instance.child_callback_id)

        else:
            # For each dependency
            for d in self.dependencies:
                # Pre process command to determine if there is a special execution technique

                ex = self.dependency_executor
                prereq_cmd = Command(self.dependency_executor, d['prereq_command'], self.name, self.guid, self.description, self.platforms, self.timeout, self.args)

                # Clean and execute prereq cmd
                self.api_instance.clean_cmd(prereq_cmd)

                output = await self.api_instance.execute_task(prereq_cmd)

                # There is no output, usually this is from a timeout
                if output is None:
                    raise Exception(f'prereq_command task execution timed out')

               # If the test fails, execute the get_prereq_command(s)
                # TODO, this seems like bad code, since i am repeating myself, could be made more elegant, but it works :)
                if "Test Passed" not in output:
                    print(f"[-] Prereqs not met for test: {self.name}, running get_prereq_command ")
                    # Run get_prereq_command
                    get_prereq_cmd = Command(self.dependency_executor, d['get_prereq_command'], self.name, self.guid, self.description, self.platforms, self.timeout, self.args)
                    self.api_instance.clean_cmd(get_prereq_cmd)
                    output = await self.api_instance.execute_task(get_prereq_cmd)
                    if output is None:
                        # Retry prereq_command
                        print(f"[*] Reissuing prereq_command")
                        output = await self.api_instance.execute_task(prereq_cmd)
                        if output is None:
                            raise Exception(f'get_prereq_command task execution timed out')

                    if "Test Passed" not in output:
                        raise Exception(f'Failed to satisfy prerequisites for {self.name}\n\tget_prereq_command: {prereq_cmd.parameters}')

    # Run the TTP
    async def run_executor(self, special_exec, method):
        p = []
        cmd = Command(self.executor["name"], self.executor["command"], self.name, self.guid, self.description, self.platforms, self.timeout, self.args)
        self.api_instance.clean_cmd(cmd)
        if special_exec:
            if method == "pe":
                cmd.set_ex_technique("execute_pe")
                name = re.findall(r'\b\w+\.exe\b', cmd.parameters)[0] # Regex to find <name>.exe
                if name is None:
                    raise Exception('Error parsing filename')
                # Build the command
                c = f"{''.join(name)} "
                c += " ".join(i.strip() for i in cmd.parameters.split(' ')[1:])
                # c += "'"
                cmd.set_parameters(c)

        await self.api_instance.execute_task(cmd)
        # Run cleanup_command if applicable
        if 'cleanup_command' in self.executor:
            cleanup_cmd = Command(self.executor["name"], self.executor["cleanup_command"], self.name, self.guid, self.description, self.platforms, self.timeout, self.args)
            self.api_instance.clean_cmd(cleanup_cmd)
            print(f"[+] Cleaning up with '{cleanup_cmd.ex_technique} {cleanup_cmd.parameters}'")
            await self.api_instance.execute_task(cleanup_cmd)