### High
- Add support to run by GUID

- If a dead beacon is detected, log the previous command that likely killed it

- When a beacon is spawned, update its config variables (spawnto), also update parent and child on start

### Medium
- Just run cleanup commands (specify by GUID maybe) (in case a beacon dies when dumping lsass or something)

- Log the attack type (ex. T1003.001)

- Config file
### Low
- Write unit tests or whatever

- Keep notes of if some tests/ GUIDs are associated with an APT

- better logic in prereq command function so im not repeating myself

- ps-import powershell scripts

- config file

- infinite loop

- method of spawning beacon is sigged -- will never spawn a new beacon

- Purge dead callbacks

### Issues
- Evasive testing - i dont have mcuh and my infra sucks lol