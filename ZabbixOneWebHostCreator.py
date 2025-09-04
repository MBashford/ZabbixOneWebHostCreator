#!/usr/bin/env python 
"""A tool for automating zabbix host creation and deletion
using informaiton retrieved from OneWeb API """
__author__ = "Milo Bashford"

import argparse
import configparser
import datetime
import os
import requests
import schedule
import signal
import sys
import time
import threading

from typing import Union
from zabbix_utils import ZabbixAPI


# Only works with pzthon version 3.11 - 3.11.9

# TO DO
# ---------
# 1. Store templategroup, template and hostgroup IDs in Creator Context
# 2. Propogate host deletion/update from remote api // not desired
# 3. parent host creator with specific api implementations inheritinng core funcitonality
# 4. Make hostgroup/template/templategroups creation not default behavior
# 5. Add extra fieldss to host inventories
# macros:
#   UT_PRODUCT_ID : like SC-938947243476
# inventory:
#   MAC A IMEI
#   MAC B IMSI
#   CONTRACT NUM: like SC-93875874387523
#   DEPLOYMENT STATUS: status
# 6. Add extra bits to template creation // specifically not requested but this makes no sense to me...
# Get UT Usage Consumption
# data transformation from this.

class OneWebHostCreator:
    urls = {
        "production": {
            "Hello": "https://api.oneweb.net/hello/v1/",
            "Perf_Monitor": "https://api.oneweb.net/performanceMonitoring/v2",
            "Product_Inv": "https://api.oneweb.net/api/webservices/productinventory/v2/",
            "Resource_Inv": "https://api.oneweb.net/resourceInventory/v3"
        },
        "training": {
            "Hello": "https://api.oneweb.training/hello/v1/",
            "Perf_Monitor": "https://api.oneweb.training/performanceMonitoring/v2",
            "Product_Inv": "https://api.oneweb.training/api/webservices/productinventory/v2/",       # issues with this url
            "Resource_Inv": "https://api.oneweb.training/resourceInventory/v3"
        }
    }
    

    def __init__(self, conf_path=None):

        self.__log_file = ".log"
        self.__log_path = ""
        self.__log_lock = threading.Lock()

        # read config file
        self.__set_conf_path(conf_path)
        self.__parse_config()

        # create & test zabbix connection
        self.__init_zabbix_connection()

        signal.signal(signal.SIGTERM, self.__exit)
        signal.signal(signal.SIGINT, self.__exit)
        
    
    def __set_conf_path(self, conf_path):

        default_path = ".conf"

        # use default if nothing passed
        if conf_path is None:
            parsed_path = default_path
        # if file exists or path ends in .conf - assume file,
        elif os.path.isfile(conf_path) or conf_path[-5:] == ".conf":
            parsed_path = conf_path
        # othwerwise treat as dir path and use default conf name
        else:
            parsed_path = os.path.join(conf_path, default_path)
            
        self.__conf_file = parsed_path


    def __set_log_path(self, path):

        default_path = self.__log_path
        
        if path in [None, ""]:
            self.__log_path = default_path
        elif os.path.isfile(path):
            self.__log_path = path
        elif os.path.isdir(path):
            self.__log_path = os.path.join(path, default_path)
        elif os.path.isdir(os.path.dirname(path)):
            self.__log_path = path
        elif os.path.basename(path) == path:
            self.__log_path = path
        else:
            self.__log_path = default_path


    def __parse_config(self):
        try:
            if os.path.exists(self.__conf_file) == False:
                self.__write_logs("----------------------\n" +
                                "Initialising Zabbix Host Creator for OneWeb\n" +
                                "----------------------\n" +
                                "No config file found. Generating config with default values at:\n" +
                                f"{os.path.abspath(self.__conf_file)}")
                self.__gen_config()

            # read config

            conf_file = configparser.ConfigParser()
            conf_file.read(self.__conf_file)

            log_path = conf_file.get("general", "log_path")
            update_interval = conf_file.get("general", "update_interval")


            oneweb_client_id = conf_file.get("oneweb", "client_id")
            oneweb_client_secret = conf_file.get("oneweb", "client_secret")
            oneweb_api_version = conf_file.get("oneweb", "api_version")

            zabbix_username = conf_file.get("zabbix", "username")
            zabbix_password = conf_file.get("zabbix", "password")
            zabbix_server_ip = conf_file.get("zabbix", "server_ip")
            zabbix_template_group = conf_file.get("zabbix", "template_group")
            zabbix_template_group_create = conf_file.get("zabbix", "create_template_group_if_none")
            zabbix_template = conf_file.get("zabbix", "template")
            zabbix_template_create = conf_file.get("zabbix", "create_template_if_none")
            zabbix_host_group = conf_file.get("zabbix", "host_group")
            zabbix_host_group_create = conf_file.get("zabbix", "create_host_group_if_none")

            self.__set_log_path(log_path)
            self.__write_logs("----------------------\n" +
                            "Initialising Zabbix Host Creator for OneWeb\n" +
                            "----------------------\n" +
                            f"Parsing Config from: {os.path.abspath(self.__conf_file)}")
        
            # check if log file path is valid
            if log_path not in [None, ""] and log_path not in self.__log_path:            
                self.__write_logs(f"WARNING: Can't access {log_path}, logs will be generated in:\n" +
                                f"{os.path.abspath(self.__log_path)}") 

            # validate oneweb scraping interval - default to once every hour
            if update_interval.isnumeric():
                self.__update_interval = int(update_interval)
            else:
                self.__write_logs("WARNING: Can't parse update interval from config - defaulting to 3600 seconds")
                self.__update_interval = 3600

            # oneweb client id
            if oneweb_client_id != "":
                self.__oneweb_client_id = oneweb_client_id
            else:
                self.__write_logs("FATALERROR: OneWeb Client ID must not be null")
                self.__exit(status=1)

            # oneweb client secret
            if oneweb_client_secret != "":
                self.__oneweb_client_secret = oneweb_client_secret
            else:
                self.__write_logs("FATALERROR: OneWeb Client Secret must not be null")
                self.__exit(status=1)

            # oneweb API version
            if oneweb_api_version in self.urls.keys():
                self.__oneweb_api_version = oneweb_api_version
            else:
                self.__write_logs(f"FATALERROR: OneWeb api version must be one of {self.urls.keys()}")
                self.__exit(status=1)

            if zabbix_username != "":
                self.__zabbix_username = zabbix_username
            else:
                self.__write_logs("FATALERROR: Zabbix Username must not be null")
                self.__exit(status=1)

            if zabbix_password != "":
                self.__zabbix_password = zabbix_password
            else:
                self.__write_logs("FATALERROR: Zabbix Password must not be null")
                self.__exit(status=1)

            if zabbix_server_ip != "":
                self.__zabbix_server_ip = zabbix_server_ip
            else:
                self.__write_logs("FATALERROR: Zabbix Server must not be null")
                self.__exit(status=1)

            if zabbix_template_group != "":
                self.__zabbix_template_group = zabbix_template_group
            else:
                self.__write_logs(f"FATALERROR: Zabbix Template Group must not be empty")
                self.__exit(status=1)

            if zabbix_template != "":
                self.__zabbix_template = zabbix_template
            else:
                self.__write_logs(f"FATALERROR: Zabbix Template must not be empty")
                self.__exit(status=1)
            
            if zabbix_host_group != "":
                self.__zabbix_host_group = zabbix_host_group
            else:
                self.__write_logs(f"FATALERROR: Zabbix Host Group must not be empty")
                self.__exit(status=1)

            if zabbix_host_group_create.lower() == "true":
                self.__zabbix_host_group_create = True
            else:
                self.__zabbix_host_group_create = False

            if zabbix_template_group_create.lower() == "true":
                self.__zabbix_template_group_create = True
            else:
                self.__zabbix_template_group_create = False
            
            if zabbix_template_create.lower() == "true":
                self.__zabbix_template_create = True
            else:
                self.__zabbix_template_create = False

        except Exception as e:
            self.__write_logs(["FATALERROR: Unable to parse config file", str(e)])
            self.__exit(status=1)


    def __gen_config(self):
        conf_file = configparser.ConfigParser(allow_no_value=True)

        conf_file.add_section("general")
        conf_file.set("general", "log_path", "")
        conf_file.set("general", "update_interval", "3600")

        conf_file.add_section("oneweb")
        conf_file.set("oneweb", "client_id", "myClientID")
        conf_file.set("oneweb", "client_secret", "myClientSecret")
        conf_file.set("oneweb", "api_version", "production")
        
        conf_file.add_section("zabbix")
        conf_file.set("zabbix", "username", "Admin")
        conf_file.set("zabbix", "password", "zabbix")
        conf_file.set("zabbix", "server_ip", "192.168.0.57")
        conf_file.set("zabbix", "template_group", "Templates/OneWeb")
        conf_file.set("zabbix", "template", "OneWebUserTerminals")
        conf_file.set("zabbix", "host_group", "OneWebUserTerminals")
        conf_file.set("zabbix", "create_template_group_if_none", "False")
        conf_file.set("zabbix", "create_template_if_none", "False")
        conf_file.set("zabbix", "create_host_group_if_none", "False")

        with open(self.__conf_file, "w") as fp:
            conf_file.write(fp)

        self.__write_logs(["Config file sucessfully created", "Exiting Host Creator"])
        self.__exit(0)


    def __init_zabbix_connection(self):
        try:
            self.__zapi = ZabbixAPI(url=f"http://{self.__zabbix_server_ip}/zabbix/api_jsonrpc.php")
            self.__zapi.login(user=self.__zabbix_username, password=self.__zabbix_password)
        except Exception as e:
            self.__write_logs(["FATALERROR: Unable connect to zabbix server", str(e)])
            self.__exit(1)  


    def __test_oneweb_connection(self):
        """Test Connection & Credentials"""

        self.__write_logs("Testing conenction to OneWeb Api...")

        try:
            url = self.urls[self.__oneweb_api_version]["Hello"] + "/oneweb/world"
            response = requests.get(
                url=url, 
                auth=requests.auth.HTTPBasicAuth(username=self.__oneweb_client_id, password=self.__oneweb_client_secret), 
            )

            if response.status_code == 200:
                self.__write_logs("... Successful connection to OneWeb")
            elif response.status_code == 404:
                self.__write_logs("... Could not authenticate OneWeb credentials")
                raise Exception(f"{response.status_code} Error: {response.reason}")
            else:
                self.__write_logs("... Could not connect to OneWeb API")
                raise Exception(f"{response.status_code} Error: {response.reason}")
        except Exception as e:
            self.__write_logs(["FATALERROR: Unable to connect to OneWeb API", str(e)])
            self.__exit(status=1)


    def __get_oneweb_inventory(self):
        """Get all user terminals from OneWeb api"""
        try:
            url = self.urls[self.__oneweb_api_version]["Resource_Inv"] + "/userTerminal"
            params = {
                "fields": ",".join([
                    "id",     # same as imei
                    "imsi",
                    "firstSeenDate",
                    "lastSeenDate",
                    "serialNumber",
                    "name",
                    "resourceState", # online/ofline
                    "relatedParty", # this will have hns details
                    "imei", # same as id
                    "place",
                    "product",
                    "location"])
            }
            response = requests.get(
                url=url, 
                auth=requests.auth.HTTPBasicAuth(username=self.__oneweb_client_id, password=self.__oneweb_client_secret), 
                params=params)
            
            if response.status_code == 200:
                self.__oneweb_hosts = response.json()
            else:
                raise Exception(f"{response.status_code} Error: {response.reason}")
                    
        except Exception as e:
            self.__write_logs(["FATALERROR: Unable to get host data from OneWeb API", str(e)])
            self.__exit(status=1)


    def __get_product_ids(self):
        """Get array of unique product ids from returned user terminal inventory"""
        return False


    def __get_oneweb_usage(self):
        return False


    def __get_zabbix_template_group(self):
        """Check if template group with same name exists"""
        return self.__zapi.templategroup.get({
            "filter":{
                "name": self.__zabbix_template_group
            }
        })
    
    def __zabbix_template_group_exists(self):
        """Check if template group exists and create new if set"""
        try:

            temp_groups = self.__get_zabbix_template_group()

            if len(temp_groups) == 1:
                self.__write_logs(f"Zabbix Template Group {self.__zabbix_template_group} exists...")

            elif len(temp_groups) == 0:
                self.__write_logs(f"No Zabbix Template Group '{self.__zabbix_template_group}'...")

                if self.__zabbix_template_group_create == False:
                    raise Exception(f"Zabbix Template Group with name '{self.__zabbix_template_group}' does \n" +
                                    "not exist and config option 'create_template_group_if_none' is set to False")
                
                else:
                    self.__write_logs(f"attempting to create Template Group '{self.__zabbix_template_group}'...")
                    self.__zapi.templategroup.create({
                        "name": self.__zabbix_template_group
                    })

                    # check that template group successfully created
                    if len(self.__get_zabbix_template_group()) == 1:
                        self.__write_logs(f"...Template Group sucessfully created.")
                    else:
                        raise Exception(f"Unable to Create Template Group '{self.__zabbix_template_group}'")
                    
            else:
                raise Exception(f"Duplicate Template Group Names")
            
        except Exception as e:
            self.__write_logs([f"FATALERROR: {str(e)}"])
            self.__zapi.logout()
            self.__exit(status=1)       


    def __get_zabbix_template(self):
        """Check if template with same name exists"""
        return self.__zapi.template.get({
            "filter":{
                "name": self.__zabbix_template
            }
        })
    

    def __zabbix_template_exists(self):
        try:

            temps = self.__get_zabbix_template()

            if len(temps) == 1:
                self.__write_logs(f"Zabbix Template {self.__zabbix_template} exists...")

            elif len(temps) == 0:
                self.__write_logs(f"No Zabbix Template '{self.__zabbix_template}'...")

                if self.__zabbix_template_create == False:
                    raise Exception(f"Zabbix Template with name '{self.__zabbix_template}' does \n" +
                                    "not exist and config option 'create_template_if_none' is set to False")
                
                else:
                    self.__write_logs(f"attempting to create Template '{self.__zabbix_template}'...")

                    # get template group id
                    template_group = self.__get_zabbix_template_group()
                    if len(template_group) != 1:
                        raise Exception(f"Template group {self.__zabbix_template_group} does not exist")

                    self.__zapi.template.create({
                        "host": self.__zabbix_template,
                        "groups": {
                            "groupid": template_group[0]["groupid"]
                        },
                        "macros": [
                            {
                                "macro": "{$CLIENT.ID}",
                                "value": self.__oneweb_client_id
                            },
                            {
                                "macro": "{$CLIENT.SECRET}",
                                "value": self.__oneweb_client_secret
                            },
                            {
                                "macro": "{$REMOTE.IMEI}",
                                "value": "355866000264312"
                            }
                        ],
                    })

                    # check that template successfully created
                    template = self.__get_zabbix_template()
                    if len(template) == 1:
                        self.__write_logs(f"...Template sucessfully created.")
                    else:
                        raise Exception(f"Unable to Create Template '{self.__zabbix_template}'")
                    
                    # create template level items
                    # ---------------------------

                    self.__zapi.item.create({
                        "name": "Get Resource Inventory Data",
                        "delay": "5m",
                        "hostid": template[0]["templateid"],
                        "key_": "Get.Resource.Inventory.Data",
                        "type": 19,
                        "url": self.urls[self.__oneweb_api_version]["Resource_Inv"] + "/userTerminal/{$REMOTE.IMEI}",
                        "authtype": 1,
                        "password": "{$CLIENT.SECRET}",
                        "username": "{$CLIENT.ID}",
                        "value_type": 4,
                        "query_fields": [
                            {
                                "name": "fields", 
                                "value": ",".join([
                                    "id",
                                    "imsi",
                                    "firstSeenDate",
                                    "lastSeenDate",
                                    "serialNumber",
                                    "name",
                                    "resourceState",
                                    "relatedParty",
                                    "imei",
                                    "place",
                                    "location"
                                ])
                            }
                        ]
                    })

                    # get the id of "Get Resource Inv Data" item assoc. with this template
                    item = self.__zapi.item.get({
                        "filter": {
                            "hostid": template[0]["templateid"]
                        }
                    })

                    # create dependent items
                    self.__zapi.item.create({
                        "name": "User Terminal Status",
                        "hostid": template[0]["templateid"],
                        "key_": "User.Terminal.Status",
                        "type": 18,
                        "value_type": 4,
                        "master_itemid": item[0]["itemid"],
                        "preprocessing": [
                            {
                                "type": 12,
                                "params": "$[0].resourceState",
                                "error_handler": 0
                            }
                        ]
                    })

                    # create template level triggers
                    # ------------------------------
                    self.__zapi.trigger.create({
                        "description": "User Terminal Down",
                        "priority": "4",
                        "expression": f"""last(/{self.__zabbix_template}/User.Terminal.Status)<>"online" """,
                    })
                    
            else:
                raise Exception(f"Duplicate Template Names")
            
        except Exception as e:
            self.__write_logs([f"FATALERROR: {str(e)}"])
            self.__exit(status=1)  


    def __get_zabbix_host_group(self):
        """Check if host group with same name exists"""
        return self.__zapi.hostgroup.get({
            "filter":{
                "name": self.__zabbix_host_group,
            }
        })
    

    def __zabbix_host_group_exists(self):
        """Check if host group exists and create new if config option set"""
        try:

            host_groups = self.__get_zabbix_host_group()

            if len(host_groups) == 1:
                self.__write_logs(f"Zabbix Host Group {self.__zabbix_host_group} exists...")

            elif len(host_groups) == 0:
                self.__write_logs(f"No Zabbix Host Group '{self.__zabbix_host_group}'...")

                if self.__zabbix_host_group_create == False:
                    raise Exception(f"Zabbix Host Group with name '{self.__zabbix_host_group}' does \n" +
                                    "not exist and config option 'create_host_group_if_none' is set to False")
                
                else:
                    self.__write_logs(f"attempting to create Host Group '{self.__zabbix_host_group}'...")
                    self.__zapi.hostgroup.create({
                        "name": self.__zabbix_host_group
                    })

                    # check that host group successfully created
                    if len(self.__get_zabbix_host_group()) == 1:
                        self.__write_logs(f"...Host Group sucessfully created.")
                    else:
                        raise Exception(f"Unable to Create Host Group '{self.__zabbix_host_group}'")
                    
            else:
                raise Exception(f"Duplicate Host Group Names")
            
        except Exception as e:
            self.__write_logs([f"FATALERROR: {str(e)}"])
            self.__zapi.logout()
            self.__exit(status=1)       


    def __get_zabbix_host(self, name):
        """Check if host with same name exists"""
        return self.__zapi.host.get({
            "filter":{
                "name": name,
            }
        })


    def __create_zabbix_host(self, name, tags=[], macros=[], inventory={}):
        """"""
        try:

            if len(self.__get_zabbix_host(name)) != 0:
                #raise Exception(f"Host with name '{name}' already exists")
                return 0
            else:
                # get hostgroup id
                hostgroup = self.__get_zabbix_host_group()
                # get tempolate id
                template = self.__get_zabbix_template()

                self.__zapi.host.create({
                    "host": name,
                    "groups": [
                        {"groupid": hostgroup[0]["groupid"]}
                    ],
                    "tags": tags,
                    "templates": [
                        {"templateid": template[0]["templateid"]}
                    ],
                    "macros": macros,
                    "inventory": inventory,
                })

                # check that host is created
                if len(self.__get_zabbix_host(name)) != 1:
                    self.__write_logs(f"Unable to create host '{name}'")
                    return 0
                else:
                    return 1

        except Exception as e:
            self.__write_logs([f"FATALERROR: Unable create zabbix Host {name}", str(e)])
            self.__exit(status=1)


    def __write_logs(self, entry: Union[str, list]):
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
            f_path = os.path.join(self.__log_path, self.__log_file)
            pad = "                          "
            if type(entry) == str:
                entry = entry.splitlines()
            lines = [l.lstrip() for l in entry]

            self.__log_lock.acquire()

            with open(f_path, "a") as file:
                start = True
                for l in lines:
                    file.write(f"{ts if start else pad} :: {l} \n")
                    start = False
                    
            self.__log_lock.release()

        except Exception as e:
            print("ERROR: Logging failed - This may or may not be critical", file=sys.stderr)
            print(e, file=sys.stderr)
            print(entry, file=sys.stderr)

    
    def __create_hosts_from_oneweb(self):

        self.__write_logs("Starting host import...")

        # Get OneWeb Hosts
        self.__get_oneweb_inventory()

        # Make Hosts
        created_hosts = 0
        for host in self.__oneweb_hosts:
            created_hosts += self.__create_zabbix_host(
                name=host["name"],
                tags=[
                    {"tag": "IMEI", "value": host["imei"]},
                    {"tag": "IMSI", "value": host["imsi"]},
                ],
                macros=[
                    {"macro": "{$REMOTE.IMEI}", "value": host["imei"]},
                ],
                inventory={
                    "type": host["place"]["externalId"],
                    "serialno_a": host["serialNumber"],
                    "location_lat": host["location"]["features"][0]["geometry"]["coordinates"][0],
                    "location_lon": host["location"]["features"][0]["geometry"]["coordinates"][1],
                }
            )

        self.__write_logs(f"Host import completed: {created_hosts} new zabbix hosts created.")

        # flush hosts after creation
        self.__oneweb_hosts = []

        
    def __exit(self, status=0, *args):
        try:
            
            if self.__log_lock.locked():
                self.__log_lock.release()

            self.__zapi.logout()

            self.__write_logs("---------------------\n" +
                            "Terminating Zabbix Host Creator for OneWeb\n" +
                            "---------------------")
        
        except AttributeError as e:
            pass
        except Exception as e:
            print(e)

        finally:
            sys.exit(status)
     


    def main(self):

        try:
            # test credentails & connection to oneweb
            self.__test_oneweb_connection()


            # Check for & Create Template Group, Template & Host Groups
            self.__write_logs("Checking for Zabbix Template and Host Groups...")
            self.__zabbix_template_group_exists()
            self.__zabbix_template_exists()
            self.__zabbix_host_group_exists()


            self.__write_logs(f"Scheduling host creation for every: {self.__update_interval} seconds\n" + 
                            "API OPTIONS \n" +
                            "----------------\n" +
                            f"CLIENT ID: {self.__oneweb_client_id}\n" +
                            f"CLIENT SECRET: {self.__oneweb_client_secret}\n" +
                            f"VERSION: {self.__oneweb_api_version}")
            
            # run now
            self.__create_hosts_from_oneweb()

            # set up scheduling...
            if self.__update_interval > 0:
                schedule.every(self.__update_interval).seconds.do(lambda func: threading.Thread(target=func).start(), self.__create_hosts_from_oneweb)
                while True:
                    schedule.run_pending()
                    time.sleep(1)
            else:
                self.__exit(status=0)

        except Exception as e:
            self.__write_logs(f"FATALERROR: {str(e)}")
            self.__exit(status=1)


if __name__ == "__main__":

    # get passed args
    psr = argparse.ArgumentParser()
    psr.add_argument("-c", "--conf-path", type=str)
    args = psr.parse_args()

    cr = OneWebHostCreator(conf_path=args.conf_path)
    cr.main()

