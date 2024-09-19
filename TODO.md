### High
- Add whitelist for binaries to run through special execution techniques in config file
    - Add preprocessing step to alter prereq cmds based on if the tool in the cofig file
    - Add dir on host (running script) for tools (Payloads/dotnet, Payloads/powershell, Payloads/pe)
        - Alter prereq to check if the file is in these dirs

- Problem: no good way to tell if there other prereqs to satisfy when doing a special execution
    - Ex. t1003.001 mimikatz needs to be installed and it needs a dump file to exist on disk
        - Hard to create logic to generally handle all of these
    - Current solution: most tests dont have multiple prereqs, currently just register the file and run the cmd
        - Most of the prereqs are going to be installing the jawn anyways

- Add support to spawn beacon in different way (idk what different way)

- Add support to run by GUID

- If a dead beacon is detected, log the previous command that likely killed it

- Add support to spawn beacon in different way (idk what different way)

- Check if the an assembly is already registered before registering it

### Medium
- Just run cleanup commands (specify by GUID maybe) (in case a beacon dies when dumping lsass or something)

- Log the attack type (ex. T1003.001)

### Low
- Write unit tests or whatever

- Keep notes of if some tests/ GUIDs are associated with an APT

- better logic in prereq command function so im not repeating myself

- ps-import powershell scripts

- method of spawning beacon is sigged -- will never spawn a new beacon

- Purge dead callbacks