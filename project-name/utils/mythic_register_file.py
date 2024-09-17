import json 
import requests
import urllib3
from mythic import mythic
from mythic import mythic_utilities as mu

url = "https://localhost:7443"
graphql = "/graphql/"
register_api = "/api/v1.4/task_upload_file_webhook"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

async def register_assembly_to_callback(callback_id, assembly_guid, mythic_instance, timeout):
    mutation = """
    mutation createTasking($callback_id: Int, $command: String!, $params: String!, $files: [String], $tasking_location: String, $parameter_group_name: String) {
        createTask(
            callback_id: $callback_id
            command: $command
            params: $params
            files: $files
            tasking_location: $tasking_location
            parameter_group_name: $parameter_group_name
        ) {
            status
            id
            error
            __typename
        }
    }
    """

    # Set the variables for the mutation
    variables = {
        "callback_id": int(callback_id),
        "command": "register_assembly",
        "params": "{\"file\":\"ASSEMBLY_GUID\"}".replace("ASSEMBLY_GUID", assembly_guid),
        "files": [assembly_guid],
        "tasking_location": "modal",
        "parameter_group_name": "Default"
    }

    try:
        submission_status= await mu.graphql_post(
            mythic=mythic_instance,
            query=mutation,
            variables=variables
        )
        if submission_status["createTask"]["status"] == "success":
            result = await mythic.waitfor_for_task_output(
                mythic=mythic_instance,
                task_display_id=submission_status["createTask"]["id"],
                timeout=timeout,
            )
            result = result.decode('UTF-8')
            if result is not None:
                return result
            else:
                raise Exception("Failed to get result back from waitfor_task_complete")
        else:
            raise Exception(f"Failed to create task: {submission_status['createTask']['error']}")
    except Exception as e:
        print(f"Error registering assembly: {str(e)}")

def register_new_assembly(assembly_name, auth_token):
    files = {'file': (assembly_name, open(assembly_name, 'rb'))}
    headers = {
        "Authorization" : "Bearer {}".format(auth_token)
    }

    r = requests.post(url + register_api, files=files, headers=headers, verify=False)
    resp = json.loads(r.text)
    if resp['status'] != 'success':
        raise Exception("Handle error in register_new_assembly")
    print(f"[*] Registered file {assembly_name} at GUID {resp['agent_file_id']}")
    return resp['agent_file_id']

def auth(username, password):
    data = {
        "username" : username,
        "password" : password
    }
    r = requests.post(url + "/auth", data=json.dumps(data), verify=False)

    return json.loads(r.text)["access_token"]

async def post(mythic, gql, query, variables):
    await mu.graphql_post(mythic, gql, query, variables)