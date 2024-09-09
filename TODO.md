### High
- Add support for check elevation (bc i am not doing it) (everything works from domainadmin account (lol))
	- Also add support to check supported platforms, gather info on the system running on during setup (platform, arch, maybe tools installed?)

### Medium
- Just run cleanup commands (specify by GUID maybe) (in case a beacon dies when dumping lsass or something)

- Log the attack type (ex. T1003.001)

- Run tests based on the GUID


### Low
- Aggregate executor names
	- Build out cases for each
	- Can't run stuff thats manual

- Write unit tests or whatever

- Keep notes of if some tests/ GUIDs are associated with an APT

- better logic in prereq command function so im not repeating myself

- ps-import powershell scripts

- config file

- infinite loop

- method of spawning beacon is sigged -- will never spawn a new beacon

### Issues
- Evasive testing - i dont have mcuh and my infra sucks lol