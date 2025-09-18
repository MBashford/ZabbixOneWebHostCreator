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

If there is no **.conf** file in this directory, running the host creator script with `python zabbixHostCreator.py` will cause it to generate a sample config file in the module root directory and then exit.

It is also possible to have Zabbix Host Creator for OneWeb search for a config file outside of its' root directory by passing a file or directory path using either `python zabbixHostCreator.py -c <path-to-config-file>` or `python zabbixHostCreator.py --conf-path <path-to-config-file>`. The script will attempt to generate a config file at this location if one is not found.

The config file contains the following sections:

### General ###
Contains options specifying the log output file and for scheduling repeat host creation. 

Option | Description
-- | --
log_path | path to the log file or directory, the directory must already exist. If no file name is specified the default name `zabbixHostCreator.log` will be used. Leaving this seting blank will cause logs to be written in the modules root directory.
update_interval | specifies the time between repeat script executions in seconds when using the built-in scheduler. Setting this to 0 or blank will disable the built-in scheduler and cause the host-creator script to run only once.

Zabbix Host Creator for OneWeb must be restarted for settings changes to take effect.

### OneWeb ###
Specify the credentials and OneWeb API target version for retriveing host data.
Option | Description
-- | --
client_id | unique application identifier for accessing the OneWEb API, must not be blank
client_secret | application password for accessing the OneWEb API, must not be blank
api_version | specify which version of the API to make request to, must be either "testing" or "production". Set as production for normal use.

Access to the OneWeb developer portal is requred to access the client ID and secret. Once logged in, navigate to `My applications` in the navigation bar (found at `https://eu1.anypoint.mulesoft.com/exchange/applications/`) and select the desired application. The below screenshot shows where to find the Client ID and Client Secret on the applicaiton page:  

<img width="1253" height="749" alt="Image" src="https://github.com/user-attachments/assets/b29f477c-21c8-46cc-ae46-c2532b002cee" />

### Zabbix ###
Options for connecting to remote Zabbix server, and controlling the behaviour of host creation
Option | Description
-- | --
username | usename for connecting to zabbix server, the user must have permissions to create and edit hosts (and/or host groups/templates/ template groups if desired...)
password | password for above Zabbix user
server_ip | IP address for the remote zabbix server where hosts shopuld be created
template_group | the template group created hosts will belong to
template | the template the created hosts will belon to
host_group | the host group the created hosts will belong to
create_template_group_if_none | determines behaviour if the above template group does not exist, if True the script will attempt to create a template group with the above name, if False then the script will fail. Defaults to False.
create_template_if_none | determines behaviour if the above template does not exist, if True the script will attempt to create a template with the above name, if False then the script will fail. Defaults to False.
create_host_group_if_none | determines behaviour if the above host group does not exist, if True the script will attempt to create a host group with the above name, if False then the script will fail. Defaults to False.


## Running Zabbix Host Creator for OneWeb ##
This is as simple as calling `python zabbixHostCreator.py`, however for reliability it is recommended to either add Zabbix Host Creator for OneWeb as a service, or run it using an external scheduler such as crontab. NOTE!: if using an external scheduler make sure to set the update_interval setting to 0 in the configuration file - this will disable the built-in scheduler. A sample service file for linux systems **zabbixHostCreatorforOneWeb.service** can be found in the install directory or in the git repo. 

### Running as a Service in Linux ###
First, ensure that zabbixHostCreatorforOneWeb.py is set as an executable using `chmod +x zabbixHostCreator.py`, then locate and open the sample **zabbixHostCreatorforOneWeb.service** file.
```
WorkingDirectory = <path-to-zabbixHostCreatorforOneWeb-root-directory>  
ExecStart = <path-to-zabbixHostCreatorforOneWeb-root-directory>/zabbixHostCreator.py
```

Edit the above fields  in the service file to point at the directory containing zabbixHostCreator.py, then copy **zabbixHostCreatorforOneWeb.service** to the `/etc/systemd/system` directory. If running Zabbix Host Creator for OneWeb from a virtual envionment set the 'ExecStart' option as:

`ExecStart = <path-to-virtual-env>/bin/python <path-to-zabbixHostCreatorforOneWeb-root-directory>/zabbixHostCreator.py`  

For deployment in production environments it is also recommended to set `Restart=always` so that the service will restart should it exit unexpectedly. Below is an example service file showing Zabbix Hsot Creator for OneWeb running using a virtual environment located in `/etc/zabbixHostCreatorforOneWebVenv` and a config file located outside of the working directory in `/var/configs`   

```
#
# /etc/systemd/system/zabbixHostCreatorforOneWeb.service
#

[Unit]
Description=ZabbixHostCreatorForOneWeb: Creates Zabbix Hosts using data periodically retrieved from OneWeb APIs
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zabbixHostCreatorforOneWeb/
ExecStart=/etc/zabbixHostCreatorforOneWeb/bin/python /etc/zabbixHostCreatorforOneWeb/zabbixHostCreatorforOneWeb.py --conf-path /var/configs/zabbixHostCreatorforOneWeb.conf
Restart=no

[Install]
WantedBy=multi-user.target
```

Execute `systemctl daemon-reload` to reload the systemd configuration, you should then be able to start and stop the pylicator service with `systemctl start zabbixHostCreatorforOneWeb.service` and `systemctl stop zabbixHostCreatorforOneWeb.service`. Use `systemctl status zabbixHostCreatorforOneWeb.service` to verify that the service is running correctly. Set Zabbix Host Creator to start on system boot with `systemctl enable zabbixHostCreatorforOneWeb.service`.

## Script Behaviour ##

### Template Group Creation ###
If determined in setting will attempt to create an empty template group with the name defined in config file. ysing zabbix api method `templategroup.create`

### Template Creation ###
If determined in setting will attempt to create a template with the name defined in config file. ysing zabbix api method `templategroup.create`

create template with folowing macros

Macro | Value
--|--
{$CLIENT.ID} | Client ID credential for OneWeb API from config file
{$CLIENT.SECRET} | Client secret/password credential for OneWeb API from config file
{$REMOTE.IMEI} | 355866000264312, default integer value, required for template lecel item creation. Gets overwritten by host level values at host creation

crete followitn template level items:

Item | Value
--|--

crete followitn template level dependent items:

Item | Value
--|--

triggers

Trigger

### Host Group Creation ###
If determined in setting will attempt to create an empty host group with the name defined in config file. ysing zabbix api method `hostgroup.create`

### Host Creation ###
`host.create`

Tags | Value
--|--

Macros | Value
--|--

Inventory | Value
-- | --

## Planned Featues ##
-TBD

## Contributors ##
- Milo Bashford (<milo.bashford@gmail.com>)

## License ##
Zabbix Host Creator for OneWeb is free software that is made available under the MIT license.

