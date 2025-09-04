# Zabbix Host Creator for OneWeb #
A python tool for creating Zabbix Hosts from OneWeb APIs

## Getting Zabbix Host Creator for OneWeb ##
Zabbix Host Creator for OneWeb requires Python 3.8 or above. Whatever method used to download the package, it is recommended to run it from a python virtual environment. Start by creating and navigting into a directory for the project with `mkdir zabbixHostCreatorforOneWeb` & `cd zabbixHostCreatorforOneWeb`.

Then create a python virtual environment named zabbixHostCreatorforOneWebVenv within the directory using:  

`python -m venv zabbixHostCreatorforOneWebVenv`  

And activate the virtual environment using:  

`source zabbixHostCreatorforOneWebVenv/bin/activate`

Now install Zabbix Host Creator for OneWeb using one of the below methods

### Install using PIP ###
To install the latest stable version usig pip:  
`pip install git+https://github.com/MBashford/ZabbixOneWebHostCreator.git`

### Cloning the git repo ###
Alternatively, clone the git repo with:  
`git clone https://github.com/MBashford/ZabbixOneWebHostCreator.git`

Cloning the repo will require dependencies to be installed separately. Do this manually or by running `python setup.py install` from the Zabbix Host Creator for OneWeb root directory.

## Configuration ##
Once installed locate the config file, **.conf**, in the Zabbix Host Creator for OneWeb root directory. If installed via pip, this location can be found with:  
`pip show zabbixHostCreatorforOneWeb`

If there is no **.conf** file in this directory, running the hsot cretor script with `python zabbixHostCreator.py` will cause it to generate a sample config file in the module root directory and then exit.

It is also possible to have Zabbix Host Creator for OneWeb search for a config file outside of its' root directory by passing a file or directory path using either `python zabbixHostCreator.py -c <path-to-config-file>` or `python zabbixHostCreator.py --conf-path <path-to-config-file>`. The script will attempt to generate a config file at this location if one is not found.

The config file contains the following sections:

### General ###
Contains options specifying the log output file and for scheduling repeat host creation. 

Option | Description
-- | --
log_path | path to the log file or directory, the directory must already exist. If no file name is specified the default name `zabbixHostCreator.log` will be used. Leaving this seting blank will cause logs to be written in the modules root directory.
update_interval* | specifies the time between repeat script executions in seconds when using the built-in scheduler. Setting this to 0 or blank will disable the built-in scheduler and cause the host-creator script to run only once.

*Note ip spoofing not supported on some windows versions, setting this to True may cause traps to be lost

Pylicator must be restarted for settings changes to take effect.

### Forwarding Rules ###
Defines forwarding behaviour for traps recieved from different IPv4 addresses. Multiple forwarding destinations can be assigned to each origin. Rules are defined as key-value pairs with the stucture 
"\<origin\> = \<destination 1\> \<destination 2\>". At present only IPv4 addresses are accepted. Below are some valid example rules:  
```
58.113.42.112 = 86.34.127.50:162
0.0.0.0/0 = 172.0.0.1:162 192.168.1.86:162
172.0.0.1/32 = 172.0.0.1:5432 192.168.0.1
```

If no destination port is specified in a rule, port 162 will be used by default.


## Running Pylicator ##
This is as simple as calling `python pylicator.py`, however for reliability it is recommended to add pylicator as a service. The sample service file for linux systems **pylicator.service** can be found in the pylicator install directory or in the git repo. 

### Running as a Service in Linux ###
First, ensure that pylicator.py is set as an executable using `chmod +x pylicator.py`, then locate and open the sample **pylicator.service** file.
```
WorkingDirectory = <path-to-pylicator-root-directory>  
ExecStart = <path-to-pylicator-root-directory>/pylicator.py
```

Edit the above fields  in the service file to point at the directory containing pylicator.py, then copy **pylicator.service** to the `/etc/systemd/system` directory. If running Pylicator from a virtual envionment set the 'ExecStart' option as:

`ExecStart = <path-to-virtual-env>/bin/python <path-to-pylicator-root-directory>/pylicator.py`  

For deployment in production environments it is also recommended to set `Restart=always` so that the pylicator service will restart should it exit unexpectedly. Below is an example service file showing Pylicator buing run using a virtual environment located in `/etc/pylicatorVenv` and a config file located outside of the working directory in `/var/configs`   

```
#
# /etc/systemd/system/pylicator.service
#

[Unit]
Description=Pylicator: Redirects incoming SNMP traps
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/pylicator/
ExecStart=/etc/pylicatorVenv/bin/python /etc/pylicator/pylicator.py --conf-path /var/configs/pylicator.conf
Restart=no

[Install]
WantedBy=multi-user.target
```

Execute `systemctl daemon-reload` to reload the systemd configuration, you should then be able to start and stop the pylicator service with `systemctl start pylicator.service` and `systemctl stop pylicator.service`. Use `systemctl status pylicator.service` to verify that pylicator is running correctly. Set Pylicator to start on system boot with `systemctl enable pylicator.service`.

## Planned Featues ##
- Optional load-balancing for traps forwarded to multiple destinations
- Track metrics for recieved traps, frequency by origin subnet, destination, etc.

## Contributors ##
- Milo Bashford (<milo.bashford@gmail.com>)

## License ##
Pylicator is free software that is made available under the MIT license.

