import os
import re 

def expand_cmd(cmd, method):
    binpath = ""
    if method == "pe":
        print("fuck you")

    elif method == "dotnet":
        name = re.findall(r"\b\w+\.exe\b", cmd.parameters)[
            0
        ]  # Regex to find <name>.exe
        for root, dirs, files in os.walk("payloads"):
            if name in files:
                binpath = os.path.join(root, name)
                
        print(binpath)