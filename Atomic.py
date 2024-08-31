import argparse
from mythic import mythic
import re
import yaml

class Atomic:
    def __init__(self, file, api, api_instance, timeout):
        self.api = api
        self.api_instance = api_instance
        self.file = file
        self.timeout = timeout

        self.parse_yaml()

    def load_atomic_yaml(self):
        with open(self.file, 'r') as file:
            self.yaml = yaml.safe_load(file)

    def parse_yaml(self):
        self.load_atomic_yaml()

        self.attack_technique = self.yaml['attack_technique']
        self.display_name = self.yaml['display_name']
        self.tests = [AtomicTest(dict(x), self.api, self.api_instance, self.timeout) for x in self.yaml['atomic_tests']]

class AtomicTest:
    def __init__(self, test, api, api_instance, timeout):
        self.api = api
        self.api_instance = api_instance
        self.atomics_folder = 'C:\\temp\\ART'
        self.name = test['name']
        self.guid = test['auto_generated_guid']
        self.description = test['description']
        self.platforms = test['supported_platforms']
        self.args = test.get('input_arguments', {})
        self.depencency_executor = test.get('dependency_executor_name', {})
        self.dependencies = test.get('dependencies', {})
        self.executor = test.get('executor', {})
        self.timeout = timeout

    def print_args(self):
        print('Input Arguments')
        for arg, value in self.args.items():
            print(f' {arg}:\n\t{value['description']}\n\t{value['default']}')

    async def check_prereqs(self):
        for d in self.dependencies:
            """
            ART will check if a file exists in some prereqs by running something similar to `if (Test-Path "#{file}") {exit 0} else {exit 1}`.
            This doesn't really work with C2 tasking, so replace it with "Test Passed and Test Failed"
            """
            cmd = d['prereq_command'].replace('exit 0', 'echo "Test Passed"')
            cmd = cmd.replace('exit 1', 'echo "Test Failed"')
            cmd = self.strip_args(cmd)

            # Execute prereqtest
            output = await self.execute_task('powershell', cmd, 7)

            # If the test fails, execute the get_prereq_command(s)
            if "Test Failed" in output:
                cmd = d['get_prereq_command']
                cmd = self.strip_args(cmd)
                print(cmd)
                output = await self.execute_task('powershell', cmd, 7)

    # Run the TTP
    # TODO, check elevation_required
    async def run_executor(self):
        # Run command
        cmd = self.executor['command']
        cmd = self.strip_args(cmd)
        await self.execute_task(self.executor['name'], cmd, 7)
        # Run cleanup_command
        cmd = self.executor['cleanup_command']
        cmd = self.strip_args(cmd)
        await self.execute_task(self.executor['name'], cmd, 7)

    # Note for future self, this will give a timestamp for logging
    async def execute_task(self, ex_technique, parameters, callback_id):
        command_name = ex_technique
        if self.api == 'mythic':
            if ex_technique == "command_prompt":
                command_name = "shell"
            elif ex_technique == "powershell":
                command_name = "powershell"

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
            print(f"[*] Issued a task: {task}")

            output = await mythic.waitfor_for_task_output(
                mythic=self.api_instance, task_display_id=task["display_id"]        )
            output = output.decode('utf-8')
            print(f"Got output:\n{"-" * 20}\n{output}")
            return output

        except Exception as e:
            print(f"Got an exception trying to issue task: {str(e)}")

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
            # Replace defaults - if exist
            cmd = cmd.replace('PathToAtomicsFolder', self.atomics_folder)
        return cmd
