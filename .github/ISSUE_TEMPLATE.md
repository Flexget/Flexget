<!---
Before opening an issue, verify:

- Is this a feature request? Post it on https://feathub.com/Flexget/Flexget
- Did you recently upgrade? Look at the Change Log and Upgrade Actions to make sure that you don't need to make any changes to your config https://flexget.com/ChangeLog https://flexget.com/UpgradeActions
- Are you running FlexGet as a daemon? Stop it completely and then start it again https://flexget.com/CLI/daemon
- Did you search to see if the issue already exists? https://github.com/Flexget/Flexget/issues
- Did you fill out the issue template as completely as possible?

The issue template is here because it helps to ensure you submitted all the necessary information the first time, and allows us to more quickly review issues. Please fill it out correctly and do not ignore it, no matter how irrelevant you think it may be. Thanks in advance for your help with this!
--->

### Expected behaviour:

<!---
Please don't just say "it doesn't crash" or "it works". Explain what the expected result is.
--->

### Actual behaviour:

### Steps to reproduce:
- Step 1: ...

#### Config:
```
Paste FULL config and remove any personal info if config is too long, attach the file to the ticket.
If issue is with a single task, you can get get resulting configuration by running:
  flexget execute --task <NAME> --dump-config
Make sure to redact any personal information (passwords, api keys, etc) !
```
  
#### Log:
<details>
 <summary>(click to expand)</summary>

```
paste log output here
```
</details>

### Additional information:

- FlexGet version:
- Python version:
- Installation method:
- Using daemon (yes/no):
- OS and version:
- Link to crash log:

<!---
In config and debug/crash logs, remember to redact any personal or sensitive information such as passwords, API keys, private URLs and so on.

Please verify that the following data is present before submitting your issue:

- Link to a paste service or paste above the relevant config (preferably full config, including templates if present). Please make sure the paste does not expire, if possible.
- Link to a paste service or paste above debug-level logs of the relevant task/s (use `flexget -L debug execute --tasks <Task_name>`).
- FlexGet version (use `flexget -V` to get it).
- Full Python version, for example `2.7.11` (use `python -V` to get it). 
- Installation method (pip, git install, etc).
- Whether or not you're running FlexGet as a daemon.
- OS and version.
- Attach crash log if one was generated, in addition to the debug-level log. It can be found in the directory with your config file.
--->
