import argparse
import json
import logs
from mythic import mythic
import re
import sys
import yaml

class Atomic:
    # Note: callback_id=None, if using API that does not have callbacks, needs to handle not passing anything in
    def __init__(self, file, api, api_instance, timeout, logfile, callback_id=None):
        self.api = api
        self.api_instance = api_instance
        self.file = file
        self.timeout = timeout
        self.callback_id = callback_id
        self.logger = logs.Logger(logfile)

        self.parse_yaml()

    def load_atomic_yaml(self):
        with open(self.file, 'r') as file:
            self.yaml = yaml.safe_load(file)

    def parse_yaml(self):
        self.load_atomic_yaml()

        self.attack_technique = self.yaml['attack_technique']
        self.display_name = self.yaml['display_name']
        self.tests = [AtomicTest(dict(x), self.api, self.api_instance, self.timeout, self.logger, self.callback_id) for x in self.yaml['atomic_tests']] # sick list comprehension

class AtomicTest:
    def __init__(self, test, api, api_instance, timeout, logger, callback_id=None):
        self.api = api
        self.api_instance = api_instance
        self.atomics_folder = 'C:\\temp\\ART'
        self.name = test['name']
        self.guid = test['auto_generated_guid']
        self.description = test['description']
        self.platforms = test['supported_platforms']
        self.args = test.get('input_arguments', {})
        self.dependency_executor = test.get('dependency_executor_name', 'powershell')
        self.dependencies = test.get('dependencies', {})
        self.executor = test.get('executor', {})
        self.timeout = timeout
        self.callback_id = callback_id
        self.logger = logger

    # Makes the dict
    def write_log(self, command, timestamp, status, api, name, guid, desc, platform, ex, timeout, callback_id, output):
        data = [
            {
                'command':command, 
                'timestamp':timestamp,
                'status':status,
                'api':api,
                'name':name,
                'GUID':guid,
                'description':desc, 
                'platform':platform,
                'executor':ex,
                'timeout':timeout,
                'callback_id':callback_id,
                'output':output
            }
        ]
        self.logger.log(data)

    def print_args(self):
        print('Input Arguments')
        for arg, value in self.args.items():
            print(f' {arg}:\n\t{value['description']}\n\t{value['default']}')

    """
    ART will check if a file exists in some prereqs by running something similar to `if (Test-Path "#{file}") {exit 0} else {exit 1}`.
    This doesn't really work with C2 tasking, so replace it with "echo Test Passed" and "echo Test Failed".
    Process arguments from the yaml

    Returns the new command (string) and updated executor (string)
    """
    def clean_cmd(self, cmd, ex=None):
        if self.api == 'mythic':
            if ex == "command_prompt":
                ex = "shell"
            elif ex == "powershell":
                ex = "powershell"

        # Clean powershell
        cmd = cmd.replace('exit 1', 'echo \'Test Failed\'')
        cmd = cmd.replace('exit /b 1', 'echo "Test Failed"')
        cmd = cmd.replace('exit 0', 'echo "Test Passed"')
        # Kinda a hack, for some reason mythic doesnt return output for "powershell cmd /c <cmd>", so run it through "shell"
        if 'cmd /c' in cmd:
            ex = 'shell'
            cmd = cmd[cmd.find('cmd /c')+6:]

        cmd = self.strip_args(cmd)
        # Replace defaults - if exist
        cmd = cmd.replace('PathToAtomicsFolder', self.atomics_folder)
        return cmd, ex

    # YAML has args in the following format #{ARG}
    # Remove them in the command to run and replace with the argument in self.args
    def strip_args(self, cmd):
        # Find all arguments in the yaml
        arguments = re.findall(r"\#{.*?}", cmd)
        for arg in arguments:
            # Get the value inside #{} to use as key
            a = ''.join(c for c in arg if c not in '#{}')
            # Get the default value of the argument
            cmd = cmd.replace(arg, self.args.get(a).get('default'))
        return cmd

    # Checks the prereqs, returns an error
    async def check_prereqs(self):
        # For each dependency
        for d in self.dependencies:
            ex = self.dependency_executor

            # Clean and execute prereqtest
            cmd = d['prereq_command']
            cmd, ex = self.clean_cmd(cmd, ex)
            output = await self.execute_task(ex, cmd, self.callback_id)

            # If the test fails, execute the get_prereq_command(s)
            # TODO, this seems like bad code, since i am repeating myself, could be made more elegant, but it works :)
            if "Test Passed" not in output:
                print(f"[-] Prereqs not met for test: {self.name}, running get_prereq_command ")
                # Run get_prereq_command
                cmd = d['get_prereq_command']
                cmd, ex = self.clean_cmd(cmd, self.dependency_executor)
                output = await self.execute_task(ex, cmd, self.callback_id)

                # Retry prereq_command
                print(f"[*] Reissuing prereq_command")
                cmd = d['prereq_command'].replace('exit 0', 'echo "Test Passed"')
                cmd, ex = self.clean_cmd(cmd, ex)
                output = await self.execute_task(ex, cmd, self.callback_id)

                if "Test Passed" not in output:
                    print(f"[-] Failed to satisfy prerequisites for {self.name}\n\tget_prereq_command: {cmd}")
                    print(f"[-] Skipping {self.name}")
                    # TODO add proper errors and stack traces
                    return "i am an error to be changed later"
        return None

    # Run the TTP
    # TODO, check elevation_required
    async def run_executor(self):
        # Run command
        cmd = self.executor['command']
        cmd, ex = self.clean_cmd(cmd, self.executor['name'])
        await self.execute_task(ex, cmd, self.callback_id)
        # Run cleanup_command if applicable
        if 'cleanup_command' in self.executor:
            cmd = self.executor['cleanup_command']
            cmd, ex = self.clean_cmd(cmd, ex)
            await self.execute_task(ex, cmd, self.callback_id)

    # Note for future self, this will give a timestamp for logging
    async def execute_task(self, ex_technique, parameters, callback_id, timeout=None):
        timeout = self.timeout if timeout is None else timeout
        command_name = ex_technique

        # Create the task
        try:
            task = await mythic.issue_task(
                mythic=self.api_instance,
                command_name=command_name,
                parameters=parameters,
                callback_display_id=callback_id,
                timeout=self.timeout,
                wait_for_complete=True,
            )
            print(f"[*] Issued a task: '{task['command_name']} {task['original_params'].strip('\n')}' to callback ID {self.callback_id}")

            output = await mythic.waitfor_for_task_output(
                mythic=self.api_instance, task_display_id=task["display_id"]        )
            output = output.decode('utf-8')
            self.write_log(task['original_params'], task['timestamp'], task['status'], self.api, self.name, self.guid, self.description, self.platforms, command_name, self.timeout, self.callback_id, output)
            print(f"[*] Got output:\n{"-" * 20}\n{output}\n{"-"*20}")
            return output

        except Exception as e:
            print(f"[-] Got an exception trying to issue task: {command_name} {parameters} {str(e)}")

    # Some atomic prereqs assume winget is installed but don't have a backup if it isnt
    # So try to install it first :)
    # Optional TODO, instead of iex the install script, keep it in repo and upload it then run from beacon
    async def install_winget(self):
        print("[*] Checking for winget-cli installation")
        # Check if winget is installed
        cmd = 'if (Get-Command winget -ErrorAction SilentlyContinue) { echo "Test Passed" } else { echo "Test Failed" }'
        cmd, ex = self.clean_cmd(cmd, 'powershell')
        output = await self.execute_task(ex, cmd, self.callback_id)
        if "Test Passed" not in output:
            print("[-] winget not found. Installing...")
            # Install winget
            cmd = 'irm asheroto.com/winget | iex' # taken from https://github.com/asheroto/winget-install
            cmd, ex = self.clean_cmd(cmd, 'powershell')
            output = await self.execute_task(ex, cmd, self.callback_id, timeout=300) # big ol timeout since it takes a while to install
            # Le epic recursive loop, surely this wont cause the program to fail if winget cant be installed from the script
            # If Test Passed is never in the output, this will recurse forever, lol
            self.install_winget()
        print('[+] winget is installed :)')
        return
