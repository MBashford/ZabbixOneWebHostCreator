#!/usr/bin/env python 
"""A tool for automating zabbix host creation and deletion
using informaiton retrieved from OneWeb API """
__author__ = "Milo Bashford"

import requests
import json
import configparser
import os
import sys
import datetime

from typing import Union
from zabbix_utils import ZabbixAPI


# TO DO
# ---------
# 1. Store templategroup, template and hostgroup IDs in Creator Context
# 2. Propogate host deletion/update from remote api
# 3. parent host creator with specific api implementations inheritinng core funcitonality


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
    

    def __init__(self):
        self.__log_file = "creator.log"
        self.__log_path = ""
        self.__config_file = "creator.conf"
        self.__parse_config()
        self.__init_zabbix_connection()


    def __parse_config(self):
        try:
            if os.path.exists(self.__config_file) == False:
                self.__write_logs("No config file found. Generating config with default values")
                self.__gen_config()

            conf_file = configparser.ConfigParser()
            conf_file.read(self.__config_file)

            log_path = conf_file.get("general", "log_path")

            oneweb_client_id = conf_file.get("oneweb", "client_id")
            oneweb_client_secret = conf_file.get("oneweb", "client_secret")
            oneweb_api_version = conf_file.get("oneweb", "api_version")

            zabbix_username = conf_file.get("zabbix", "username")
            zabbix_password = conf_file.get("zabbix", "password")
            zabbix_server_ip = conf_file.get("zabbix", "server_ip")
            zabbix_template_group = conf_file.get("zabbix", "template_group")
            zabbix_template = conf_file.get("zabbix", "template")
            zabbix_host_group = conf_file.get("zabbix", "host_group")
            zabbix_behaviour = conf_file.get("zabbix", "behaviour")

            # perform some basic config validation

            if log_path != "" and os.path.exists(log_path):
                self.__log_path = log_path
            elif log_path != "":
                self.__write_logs(f"WARNING: Can't access directory {log_path}, logs will be generated in the local dir") 

            self.__oneweb_client_id = oneweb_client_id
            self.__oneweb_client_secret = oneweb_client_secret

            if oneweb_api_version in self.urls.keys():
                self.__oneweb_api_version = oneweb_api_version
            else:
                self.__write_logs(f"FATALERROR: OneWeb api version must be one of {self.urls.keys()}")
                exit(1)

            self.__zabbix_username = zabbix_username
            self.__zabbix_password = zabbix_password
            self.__zabbix_server_ip = zabbix_server_ip

            if zabbix_template_group != "":
                self.__zabbix_template_group = zabbix_template_group
            else:
                self.__write_logs(f"FATALERROR: Zabbix Template Group must not be empty")
                exit(1)

            if zabbix_template != "":
                self.__zabbix_template = zabbix_template
            else:
                self.__write_logs(f"FATALERROR: Zabbix Template must not be empty")
                exit(1)
            
            if zabbix_host_group != "":
                self.__zabbix_host_group = zabbix_host_group
            else:
                self.__write_logs(f"FATALERROR: Zabbix Host Group must not be empty")
                exit(1)

            if zabbix_behaviour in ["create", "update"]:
                self.__zabbix_behaviour = zabbix_behaviour
            else:
                self.__write_logs(f"FATALERROR: Zabbix beheaviour must be one of 'create', 'update'")
                exit(1)

        except Exception as e:
            self.__write_logs(["FATALERROR: Unable to parse config file", str(e)])
            exit(1)


    def __gen_config(self):
        conf_file = configparser.ConfigParser(allow_no_value=True)

        conf_file.add_section("general")
        conf_file.set("oneweb", "log_path", "")

        conf_file.add_section("oneweb")
        conf_file.set("oneweb", "client_id", "myClientID")
        conf_file.set("oneweb", "client_secret", "myClientSecret")
        
        conf_file.add_section("zabbix")
        conf_file.set("zabbix", "username", "Admin")
        conf_file.set("zabbix", "password", "zabbix")
        conf_file.set("zabbix", "server_ip", "192.168.0.57")
        conf_file.set("zabbix", "template_group", "Templates/OneWeb")
        conf_file.set("zabbix", "template", "OneWebUserTerminals")
        conf_file.set("zabbix", "host_group", "OneWebUserTerminals")
        conf_file.set("zabbix", "behaviour", "create")

        with open(self.__config_file, "w") as fp:
            conf_file.write(fp)

        self.__write_logs(["Config file sucessfully created", "Exiting Host Creator"])
        exit(0)


    def __init_zabbix_connection(self):
        try:
            self.__zapi = ZabbixAPI(url=f"http://{self.__zabbix_server_ip}/zabbix/api_jsonrpc.php")
            self.__zapi.login(user=self.__zabbix_username, password=self.__zabbix_password)
        except Exception as e:
            self.__write_logs(["FATALERROR: Unable connect to zabbix server", str(e)])
            exit(1)    


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
            exit(1)


    def __get_zabbix_template_group(self):
        """Check if template group with same name exists"""
        return self.__zapi.templategroup.get({
            "filter":{
                "name": self.__zabbix_template_group
            }
        })
    

    def __create_zabbix_template_group(self):
        try:
            if len(self.__get_zabbix_template_group()) != 0:
                if self.__zabbix_behaviour == "create":
                    raise Exception(f"Template Group with name {self.__zabbix_template_group} already exists")
                # otherwise use this template group 
                self.__write_logs(f"Template Group with name {self.__zabbix_template_group} already exists, skipping template creation")

            self.__zapi.templategroup.create({
                "name": self.__zabbix_template_group
            })

            # check that template group successfully created
            if len(self.__get_zabbix_template_group()) != 1:
                raise Exception("Internal Server Error")
            else:
                self.__write_logs(f"Template Group '{self.__zabbix_template_group}' successfully created")

        except Exception as e:
            self.__write_logs([f"FATALERROR: Unable create zabbix template group {self.__zabbix_template_group}", str(e)])
            self.__zapi.logout()
            exit(1) 


    def __get_zabbix_template(self):
        """Check if template with same name exists"""
        return self.__zapi.template.get({
            "filter":{
                "name": self.__zabbix_template
            }
        })
    

    def __create_zabbix_template(self):
        try:
            if len(self.__get_zabbix_template()) != 0:
                if self.__zabbix_behaviour == "create":
                    raise Exception(f"Template with name {self.__zabbix_template} already exists")
                # otherwise use this template
                self.__write_logs(f"Template with name {self.__zabbix_template} already exists, skipping template creation")

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
            if len(template) != 1:
                raise Exception("Internal Server Error")
            else:
                self.__write_logs(f"Template '{self.__zabbix_template}' successfully created")

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

        except Exception as e:
            self.__write_logs([f"FATALERROR: Unable create zabbix template {self.__zabbix_template}", str(e)])
            self.__zapi.logout()
            exit(1)



    def __get_zabbix_host_group(self):
        """Check if host group with same name exists"""
        return self.__zapi.hostgroup.get({
            "filter":{
                "name": self.__zabbix_host_group,
            }
        })
    

    def __create_zabbix_host_group(self):
        try:
            if len(self.__get_zabbix_host_group()) != 0:
                if self.__zabbix_behaviour == "create":
                    raise Exception(f"Host Group with name {self.__zabbix_host_group} already exists")
                # otherwise use this template
                self.__write_logs(f"Host Group with name {self.__zabbix_host_group} already exists, skipping template creation")

            else:
                self.__zapi.hostgroup.create({
                    "name": self.__zabbix_host_group
                })

        except Exception as e:
            self.__write_logs([f"FATALERROR: Unable create zabbix Host Group {self.__zabbix_template}", str(e)])
            self.__zapi.logout()
            exit(1)


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
                raise Exception(f"Host with name '{name}' already exists")
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

        except Exception as e:
            self.__write_logs([f"FATALERROR: Unable create zabbix Host {name}", str(e)])
            self.__zapi.logout()
            exit(1)


    def __write_logs(self, entry: Union[str, list]):
        try:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
            f_path = os.path.join(self.__log_path, self.__log_file)
            pad = "                          "
            if type(entry) == str:
                entry = entry.splitlines()
            lines = [l.lstrip() for l in entry]

            with open(f_path, "a") as file:
                start = True
                for l in lines:
                    file.write(f"{ts if start else pad} :: {l} \n")
                    start = False

        except Exception as e:
            print("ERROR: Logging failed - This may or may not be critical", file=sys.stderr)
            print(e, file=sys.stderr)
            print(entry, file=sys.stderr)


    def main(self):

        # Get OneWeb Hosts
        self.__get_oneweb_inventory()

        # Make Template Group, Template & Host Goupr
        self.__create_zabbix_template_group()
        self.__create_zabbix_template()
        self.__create_zabbix_host_group()

        # Make Hosts
        for host in self.__oneweb_hosts:
            self.__create_zabbix_host(
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

        # close zabbix api and exit
        self.__write_logs("DONE!")
        self.__zapi.logout()
        exit(0)


if __name__ == "__main__":
    cr = OneWebHostCreator()
    cr.main()

