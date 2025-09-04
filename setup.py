from setuptools import setup

VERSION = "0.1.0"
DESCRIPTION = "A tool for creating Zabbix Hosts from OneWeb APIs"
LONG_DESCRIPTION = """
A tool for creating Zabbix Hosts from OneWeb APIs. Incorporates a
simple built-in scheduler for repeated host creation/updating.
"""

setup(
    name="zabbixHostCreatorforOneWeb",
    version=VERSION,
    python_requires='>=3.8',
    author="Milo Bashford",
    author_email="milobashford@gmail.com",
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    packages=["zabbixHostCreatorforOneWeb"],
    install_requires=[
        "requests==2.32.3",
        "schedule==1.2.0",
        "zabbix-utils==2.0.2"
    ],
    package_dir={"": "src"},
    package_data={"zabbixHostCreatorforOneWeb": ["zabbixHostCreatorforOneWeb.service"]}
)