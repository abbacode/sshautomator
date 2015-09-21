# SSH Task Automation Tool v3.0 

==========================
Features of the script:
==========================
* Automated execution of commands over SSH
* Unique commands can be defined on a per device basis
* Multiple commands can be defined within a single task 
* Resulting output of command will be saved to a local file 
* Both Cisco and non-Cisco devices are supported (all devices which have a SSH CLI)
* Simple excel front-end to help manage the automation of task
* Multi-processing support to speed up the execution of task

=======================================================
Practical application examples for network engineers:
=======================================================
* Capturing of the running configuration from multiple devices into unique filenames
* Bulk 'copy run start' on multiple devices
* Execution of test cases and recording of results
* Clearing the counters on multiple devices
* Quick capture of specific commands from bulk set of devices to assist with auditing
* Bulk configuration updates such as SNMP, AAA, NTP settings to simplify deployment

====================
Installation notes
====================
Tested using Windows 8.1 64-bit and 32-bit running Python 3.4.2

Requirements:
* Python version 3.x
* xlrd      - use 'pip install xlrd'
* paramiko  - use 'pip install paramiko'

Paramiko will automatically try to install Crypto library and most likely fail.  The fix for this is to download the pre-compiled binary depending on the version of Python you have installed.  Make sure you remove any references to the crypto library first by typing: 'pip uninstall crypto'.

You can find the correct windows pre-compiled binaries from the following site (or alternatively search google): 
https://www.dropbox.com/s/n6rckn0k6u4nqke/pycrypto-2.6.1.zip?dl=0]

Another common problem which might occur when installing the Crypto pre-compiled binaries is that it cannot detect the Python path in the registry.  Attached is a copy of the registriy settings which point to the default install path (C:\Python34) directory.  You can double click the attached 'Python Install Path.reg' file or alternatively create the entry yourself.

=========================
Operating instructions:
=========================
* Extract the contents of the zip file into a directory
* Edit the auto.xls and define the device information (device name,ip address,username,password,cisco or non-cisco device)
* Edit the auto.xls and define the task (task no, target device, commands to run, filename to store output)
* Run the script from the command line, i.e. type 
 - python auto.py -file auto.xls 
 - python auto.py -file auto.xls -turbo


Two optional columns are found in the 'tasks' tab and are relevant for running commands on non-Cisco devices.  
 - Task delay indicates how long you should wait after executing a command before attempting to grab the output
 - Buffer size is the output in bytes that you expect to grab
 - Make sure the right delay and buffer size is specified otherwise the script will not be able to grab the full output
