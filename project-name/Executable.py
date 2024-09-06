"""
Interface for defining an executable API
"""
from abc import ABC, abstractmethod
from mythic import mythic
import re
import logs

class Executable(ABC):
    @abstractmethod
    def execute_task(self):
        pass

    """
    ART will check if a file exists in some prereqs by running something similar to `if (Test-Path "#{file}") {exit 0} else {exit 1}`.
    This doesn't really work with C2 tasking, so replace it with "echo Test Passed" and "echo Test Failed".
    Process arguments from the yaml

    Returns the new command (string) and updated executor (string)
    """
    @abstractmethod
    def clean_cmd(self):
        pass

    """
    ART will check if a file exists in some prereqs by running something similar to `if (Test-Path "#{file}") {exit 0} else {exit 1}`.
    This doesn't really work with C2 tasking, so replace it with "echo Test Passed" and "echo Test Failed".
    Process arguments from the yaml

    Returns the new command (string) and updated executor (string)
    """
    @abstractmethod
    def strip_args(self):
        pass

    @abstractmethod
    def log_write(self):
        pass

    @abstractmethod
    def log_error(self):
        pass

class IMythic(Executable):
    def __init__(self, atomics_folder, logfile):
        self.api = "Mythic"
        self.atomics_folder = atomics_folder
        self.logger = logs.Logger(logfile)

    # Login
    async def login(self, username, password):
        self.api_instance = await mythic.login(
            username=username,
            password=password,
            server_ip="localhost",
            server_port=7443,
            timeout=-1
        )
        if self.api_instance is None:
            raise Exception(f"Could not login to Mythic at {server_ip}:{server_port} with {username}:{password}")

    # Update callback info
    # TODO, use this for callback management
    async def update_callback(self, mythic_instance):
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

    # Get the callback ID
    # TODO possibly change this to get all backs?
    async def get_callback(self, hostname):
        callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)
        for c in callbacks:
            if c['host'] == hostname:
                callback_id = c['display_id']
        self.parent_callback_id = callback_id
        self.child_callback_id = callback_id
        return callback_id

    async def execute_task(self, command):
        # Create the task
        try:
            task = await mythic.issue_task(
                mythic=self.api_instance,
                command_name=command.ex_technique,
                parameters=command.parameters,
                callback_display_id=self.child_callback_id,
                timeout=command.timeout,
                wait_for_complete=True,
            )
            print(f"[*] Issued a task: '{task['command_name']} {task['original_params'].strip('\n')}' to callback ID {self.child_callback_id}")

            output = await mythic.waitfor_for_task_output(
                mythic=self.api_instance, task_display_id=task["display_id"]        )
            output = output.decode('utf-8')
            self.log_write(task['original_params'], task['timestamp'], task['status'], "mythic", command.name, command.guid, command.description, command.platforms, command.ex_technique, command.timeout, self.child_callback_id, output)
            print(f"[*] Got output:\n{"-" * 20}\n{output}\n{"-"*20}")
            return output

        except Exception as e:
            self.log_error("mythic", command.name, command.guid, command.description, command.platforms, command.timeout, self.child_callback_id, str(e))
            print(f"[-] Got an exception trying to issue task: {command.ex_technique} {command.parameters} {str(e)}")


    # Mythic specific implementation
    def clean_cmd(self, cmd):
        if cmd.ex_technique == "command_prompt":
            cmd.set_ex_technique("shell")
        elif cmd.ex_technique == "powershell":
            cmd.set_ex_technique("powershell")

        # Clean powershell
        cmd.set_parameters(cmd.parameters.replace('exit 1', 'echo \'Test Failed\''))
        cmd.set_parameters(cmd.parameters.replace('exit /b 1', 'echo "Test Failed"'))
        cmd.set_parameters(cmd.parameters.replace('exit 0', 'echo "Test Passed"'))

        # Kinda a hack, for some reason mythic doesnt return output for "powershell cmd /c <cmd>", so run it through "shell"
        if 'cmd /c' in cmd.parameters:
            cmd.set_ex_technique('shell')
            cmd.set_parameters(cmd.parameters[cmd.parameters.find('cmd /c')+6:])

        self.strip_args(cmd)
        # Replace defaults - if exist
        cmd.set_parameters(cmd.parameters.replace('PathToAtomicsFolder', self.atomics_folder))

    def strip_args(self, cmd):
        # Find all arguments in the yaml
        arguments = re.findall(r"\#{.*?}", cmd.parameters)
        for arg in arguments:
            # Get the value inside #{} to use as key
            a = ''.join(c for c in arg if c not in '#{}')
            # Get the default value of the argument
            cmd.set_parameters(cmd.parameters.replace(arg, str(cmd.args.get(a).get('default'))))

    def log_write(self, command, timestamp, status, api, name, guid, desc, platform, ex, timeout, callback_id, output):
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

    # Used to log an error in CSV, notably, 'status' is "failed"
    def log_error(self, api, name, guid, desc, platforms, timeout, callback_id, err_str):
        data = [
            {
                'command':"None", 
                'timestamp':"None",
                'status':"failed",
                'api':api,
                'name':name,
                'GUID':guid,
                'description':desc, 
                'platform':platforms,
                'executor':"None",
                'timeout':timeout,
                'callback_id':callback_id,
                'output':err_str
            }
        ]
        self.logger.log(data)

    # Some atomic prereqs assume winget is installed but don't have a backup if it isnt
    # So try to install it first :)
    # Optional TODO, instead of iex the install script, keep it in repo and upload it then run from beacon
    async def install_winget(self):
        print("[*] Checking for winget-cli installation")
        # Check if winget is installed
        cmd = Command('powershell', 'if (Get-Command winget -ErrorAction SilentlyContinue) { echo "Test Passed" } else { echo "Test Failed" }', "Test for Install Winget", "None", "Test for Install Winget", "Windows", 120)
        self.clean_cmd(cmd)
        output = await self.execute_task(cmd)
        if "Test Passed" not in output:
            print("[-] winget not found. Installing...")
            # Install winget
            cmd = Command('powershell', 'irm asheroto.com/winget | iex', "Install Winget", "None", "Install Winget", "windows", 120) # taken from https://github.com/asheroto/winget-install
            cmd, ex = self.clean_cmd(cmd, 'powershell')
            output = await self.execute_task(cmd) # big ol timeout since it takes a while to install
            # Le epic recursive loop, surely this wont cause the program to fail if winget cant be installed from the script
            # If Test Passed is never in the output, this will recurse forever, lol
            await self.install_winget()
        print('[+] winget is installed :)')
        return
