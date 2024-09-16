import json 
import requests
import urllib3

url = "https://localhost:7443"
graphql = "/graphql/"
register_api = "/api/v1.4/task_upload_file_webhook"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def register_assembly_to_callback(callback_id, assembly_guid, auth_token):
    data = {
        "operationName" : "createTasking",
        "variables" : {
            "callback_id" : int(callback_id),
            "command" : "register_assembly",
            "params" : "{\"file\":\"ASSEMBLY_GUID\"}".replace("ASSEMBLY_GUID",assembly_guid),
            "files" : [
                assembly_guid
            ],
            "tasking_location" : "modal",
            "parameter_group_name" : "Default"
        },
        "query": "mutation createTasking($callback_id: Int, $callback_ids: [Int], $command: String!, $params: String!, $files: [String], $token_id: Int, $tasking_location: String, $original_params: String, $parameter_group_name: String, $parent_task_id: Int, $is_interactive_task: Boolean, $interactive_task_type: Int, $payload_type: String) {\n  createTask(\n    callback_id: $callback_id\n    callback_ids: $callback_ids\n    command: $command\n    params: $params\n    files: $files\n    token_id: $token_id\n    tasking_location: $tasking_location\n    original_params: $original_params\n    parameter_group_name: $parameter_group_name\n    parent_task_id: $parent_task_id\n    is_interactive_task: $is_interactive_task\n    interactive_task_type: $interactive_task_type\n    payload_type: $payload_type\n  ) {\n    status\n    id\n    error\n    __typename\n  }\n}"
    }

    headers = {
        "Authorization" : "Bearer {}".format(auth_token)
    }

    r = requests.post(url + graphql, data=json.dumps(data), headers=headers, verify=False)
    print(r.text)

def register_new_assembly(assembly_name, auth_token):
    files = {'file': (assembly_name, open(assembly_name, 'rb'))}
    headers = {
        "Authorization" : "Bearer {}".format(auth_token)
    }

    r = requests.post(url + register_api, files=files, headers=headers, verify=False)
    resp = json.loads(r.text)
    if resp['status'] != 'success':
        print("Handle error in register_new_assembly")
    return resp['agent_file_id']

def auth(username, password):
    data = {
        "username" : username,
        "password" : password
    }
    r = requests.post(url + "/auth", data=json.dumps(data), verify=False)

    return json.loads(r.text)["access_token"]


"""
    if args.regnew:
        register_new_assembly(args.assembly, auth_token)
    elif args.regcallback:
        register_assembly_to_callback(args.cbid, args.guid, auth_token)
"""