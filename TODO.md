### High
1. Some idea of parent beacon, spawn new beacon to run tests, if the testing becaon dies, spawn a new one
	-. Update decription to alive, dead, possibly dead or something

2. Check after each test if becaon has died
	- Check tiemout if it hasnt checked in X amount of time after last checkin
	- Prob better to have a sample command (like powershell echo "Test Passed") to check if the beacon is alive, maybe try 2 or 3 times
	- IF beacon died, switch to backup beacon, if back up beacon dies then box is prob quarantined

3. Add support for check elevation (bc i am not doing it) (everything works from domainadmin account (lol))
	- Also add support to check supported platforms, gather info on the system running on during setup (platform, arch, maybe tools installed?)

### Medium
4. Just run cleanup commands (specify by GUID maybe) (in case a beacon dies when dumping lsass or something)

5. Log the attack type (ex. T1003.001)

6. Run tests based on the GUID


### Low
7. Aggregate executor names
	- Build out cases for each
	- Can't run stuff thats manual

8. Write unit tests or whatever

9. Keep notes of if some tests/ GUIDs are associated with an APT

10. better logic in prereq command function so im not repeating myself

11. ps-import powershell scripts

### Issues
- Evasive testing - i dont have mcuh and my infra sucks lol