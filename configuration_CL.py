import meraki
from meraki_helper import *
import batch_helper
import json
import yaml
import requests
import csv
import sys
import os
import base64
import argparse
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import datetime
import asyncio
import meraki.aio
from datetime import datetime
import logging
from termcolor import *
import colorama

"""
Assumptions:
1. Meraki Dashboard account created for your User ID and an Organization has been created in the Dashboard
2. Devices and License already claimed into the Organization. Check 'Organization> Inventory'
3. API key generated for the account under 'My Profile' page in the Dashboard
4. Script execution environment is already setup with the API Key mapped as an environment variable. Python packages installed in the environment using 'pip3 install -r requirements.txt'
5. Network and Device configs are predefined in yaml files. This will be our source of truth for configuration.
"""

border = colored('----------------------------------------------------', 'blue', attrs=['bold'])
colorama.init()

def main(api_key, site):
    # Instantiate a Meraki dashboard API session
    log_dir = os.path.join(os.getcwd(), "Logs/")
    m = meraki.DashboardAPI(
        api_key,
        wait_on_rate_limit=True,
        maximum_retries=25,
        output_log=True,
        log_file_prefix=os.path.basename(__file__)[:-3]+ "_" + str(site),
        log_path=log_dir,
        print_console=False,
    )
    
    # Read yaml files
    print(f'   Reading the Config files for Pod {site}...')
    site_dir = "Configs/CLPod0" + site.lower() + "/"
    network_file = site_dir + 'network.yml'
    device_file = site_dir + 'devices.yml'
    
    with open(network_file, "r") as stream1:
        try:
            network_data = yaml.safe_load(stream1)
        except yaml.YAMLError as e:
            print(e)

    with open(device_file, "r") as stream2:
        try:
            device_data = yaml.safe_load(stream2)
        except yaml.YAMLError as e:
            print(e)
         
    network_name = network_data["site"]
    pod_num = re.findall('\d+', network_name)[0]
    network_type = network_data["network_type"]
    network_loc = network_data["address"]["countrySubdivisionCode"]
    network_tz = timeZone(network_loc)
    network_tags = network_data["network_tags"]
    network_tags.append(network_loc)
    device_list = network_data["inventory"]["devicelist"]
    wireless_settings = network_data["wireless"]
    
    print(border)
    print(colored('STEP 2 - CREATE NETWORK AND CONFIGURE SETTINGS', 'blue', attrs=['bold']))
    print(border)
    # Get Org ID
    print("1. Get Meraki Organization details for Pod " + pod_num.lstrip('0')) 
    orgs = get_organizations(m)
    for org in orgs:
        if org["name"] == 'Cisco Live API Pod'+ pod_num.lstrip('0'):
            org_name = org["name"]
            org_id = org['id']
    print("   Meraki Organization Name: " + org_name)        
    print("   Meraki Organization ID: " + org_id)

    # Create new site network
    print("2. Create new network")
    response = create_network(m, org_id, network_name, network_type, network_tags, network_tz)
    m._logger.info("Create Network Response: ")
    m._logger.info(response)
    network_id = response["id"]
    network_nm = response["name"]
    if network_id is not None:
        print("   Network created successfully")
        print("   Network Name: " + network_nm)        
        print("   Network ID: " + network_id)
    else:
        print("   ERROR: Unable to create network!")
        
    # Configure Network alerts
    print("3. Configure Network Alert Settings")
    nw_alert_settings = network_data["alert_settings"]
    recipients = nw_alert_settings["default_recipients"]
    nw_alerts = nw_alert_settings["alerts"]
    response = configure_alerts(m, network_id, recipients, nw_alerts)
    m._logger.info("Configure Network Alerts Response: ")
    m._logger.info(response) 
    print("   Email Alerts created succesfully for following events - Rogue AP Detection, Network Gateway Down")
    
    
    print(border)
    print(colored('STEP 3 - CLAIM DEVICES AND CONFIGURE GENERAL SETTINGS', 'blue', attrs=['bold']))
    print(border)
    # Claim devices to the network
    print("1. Claim Devices to Network")
    serial_list = list()
    for device in device_list:
        device_serial = network_data["inventory"][device]["serial"]
        device_model = network_data["inventory"][device]["model"]
        print(f'   Claiming device - Serial "{device_serial}" Model "{device_model}"')
        serial_list.append(device_serial)
    response = claim_devices(m, network_id, serial_list)
    m._logger.info("Claim Devices Response: ")
    m._logger.info(response)
    print(f'   All 3 devices successfully claimed successfully to network "{network_nm}"')
 
    print("2. Configure Device Settings")
    for device in device_list:
        device_serial = network_data["inventory"][device]["serial"]
        device_name = network_data["inventory"][device]["name"]
        device_tags = network_data["inventory"][device]["tags"]
        print(f'   Configuring device {device_serial} - Name "{device_name}" and Tags {device_tags}')
        response = configure_device(m, device_serial, device_name, device_tags)
        m._logger.info(f'Configure Device {device_serial} Response: ')
        m._logger.info(response)
    print("   Devices configured successfully with name and tags")
    
    
    print(border)
    print(colored('STEP 4 - CONFIGURE MX APPLIANCE SETTINGS', 'blue', attrs=['bold']))
    print(border)
    # Configure Network Appliance Addressing & VLANs
    print("1. Configure MX Appliance VLANs")
    for device in device_list:
        if 'MX' in device:
            if 'vlans' in device_data[device].keys():
                # Enable Vlans setting for the network
                print("   Enable VLANs setting for the Network")
                response = update_network_vlan_settings(m, network_id, True)
                m._logger.info("Enable VLANs Response: ")
                m._logger.info(response)
                
                # Configure all the Vlans for the Network Appliance
                print("   Configure VLANs and Subnets")
                for vlan, config in device_data[device]["vlans"].items():
                    vlan_id = config.pop('id')
                    vlan_name = config.pop('name')
                    response = create_appliance_vlan(m, network_id, vlan_id, vlan_name, config)
                    m._logger.info(f'Configure Vlan {vlan_id} Response: ')
                    m._logger.info(response)
                    if response["id"] is not None:
                        print(f'   VLAN {vlan_id} configured')
                
                # Configure Network Appliance Port
                print("2. Configure MX Appliance Per-port VLAN Settings")
                for port, config in device_data[device]["applianceports"].items():
                    port_num = re.search(r'Port(\d+)', port).group(1)
                    response = configure_appliance_port(m, network_id, port_num, config)
                    m._logger.info(f'Configure MX Port {port_num} Response: ')
                    m._logger.info(response)
                    if response:
                        print(f'   Port {port_num} configured')

    # Configure Appliance firewall rules
    print("3. Configure MX Appliance L7 Firewall Rules")
    for device in device_list:
        if 'MX' in device:
            if 'L7FirewallRules' in device_data[device].keys():
                L7_FW_rules = device_data[device]['L7FirewallRules']
                response = create_appliance_L7FWRules(m, network_id, L7_FW_rules)
                m._logger.info("Configure L7 Firewall Response: ")
                m._logger.info(response)
                if response:
                    print(f'   Firewall Rules configured to block Facebook and BitTorrent application')
           
    
    print(border)
    print(colored('STEP 5 - CONFIGURE MS SWITCH SETTINGS', 'blue', attrs=['bold']))
    print(border)            
    # Fix - Configure Switch Management VLAN
    print("1. Configure Switch Management VLAN")
    for device in device_list:
        if 'MS' in device:
            mgmt_vlan = device_data[device]["managementVlan"]
            response = configure_switch_settings(m, network_id, mgmt_vlan)
            m._logger.info("Configure Switch  Response: ")
            m._logger.info(response)
            if response["vlan"] == mgmt_vlan:
                print(f'   Switch Management VLAN set to {response["vlan"]}')
        
    # Configure switchports
    print("2. Configure Switch Port Settings")
    for device in device_list:
        device_serial = network_data["inventory"][device]["serial"]
        device_name = network_data["inventory"][device]["name"]
        action_list_1 = list()
        if 'MS' in device:
            sw_port_count = len(device_data[device]["switchports"])
            print(f'   Configuring Ports 1 to {sw_port_count} using Action Batch')
            for port, config in device_data[device]["switchports"].items():
                port_num = re.search(r'Port(\d+)', port).group(1)
                action1 = m.batch.switch.updateDeviceSwitchPort(device_serial, port_num, **config)
                action_list_1.append(action1)
            test_helper = batch_helper.BatchHelper(m, org_id, action_list_1, linear_new_batches=True, actions_per_new_batch=50)
            test_helper.prepare()
            test_helper.generate_preview()
            test_helper.execute()
            m._logger.info(f'helper status is {test_helper.status}')
            batches_report = m.organizations.getOrganizationActionBatches(org_id)
            new_batches_statuses = [{'id': batch['id'], 'status': batch['status']} for batch in batches_report if batch['id'] in test_helper.submitted_new_batches_ids]
            failed_batch_ids = [batch['id'] for batch in new_batches_statuses if batch['status']['failed']]
            m._logger.info(f'Failed batch IDs are as follows: {failed_batch_ids}')
            if not failed_batch_ids:
                print(f'   All ports in switch {device_name} configured successfully')

    print(border)
    print(colored('STEP 6 - CONFIGURE MR ACCESS POINT SETTINGS', 'blue', attrs=['bold']))
    print(border)         
    # Configure Wireless SSIDs
    print("1. Configure Wireless SSIDs and map SSID based on AP tags")
    ssids = wireless_settings["ssids"]
    for ssid in ssids.values():
        ssid_number = ssid.pop('number')
        response = configure_ssid(m, network_id, ssid_number, ssid)
        m._logger.info("Configure SSID Response: ")
        m._logger.info(response)
        if response:
            print(f'   SSID "{response["name"]}" configured successfully')

    # Configure Wireless RF PRofiles
    print("2. Configure Wireless RF Profiles")
    rf_profiles = wireless_settings["rfprofiles"]
    rfprofilelookup = {}
    for rfp in rf_profiles.values():
        name = rfp.pop('name')
        bandType = rfp.pop('bandSelectionType')
        response = configure_rfprofile(m, network_id, name, bandType, rfp)
        m._logger.info("Configure Wireless RF Profiles Response: ")
        m._logger.info(response)
        rfp_id = response["id"]
        rfprofilelookup[name] = rfp_id
        m._logger.info(f'   RF Profile Name: {name}    RF Profile ID: {rfp_id}')
        if rfp_id is not None:
            print (f'   RF Profile "{name}" configured successfully')

    # Map AP with corresponding RF Profile based on AP tags  
    print("3. Map AP with RF Profile based on AP tags")
    for device in device_list:
        if 'MR' in device:
            ap_name = network_data["inventory"][device]["name"]
            ap_tags = network_data["inventory"][device]["tags"]
            ap_serial = network_data["inventory"][device]["serial"]
            if 'zone1' in ap_tags:
                rf_profile = rfprofilelookup["Zone1"]
                r = map_ap_rfprofile(m, ap_serial, rf_profile)
                print(f'   AP "{ap_name}" mapped to RF Profile "Zone1"')
            if 'zone2' in ap_tags:
                rf_profile = rfprofilelookup["Zone2"]
                r = map_ap_rfprofile(m, ap_serial, rf_profile)
                print(f'   AP "{ap_name}" mapped to RF Profile "Zone2"')
    
    
    print(colored('----------------------------------------------------', 'green', attrs=['bold']))
    print(colored('Network and Devices configured successfully!', 'green', attrs=['bold']))
    print(colored('Login to Meraki dashboard to validate the changes!', 'green', attrs=['bold']))
    print(colored('----------------------------------------------------', 'green', attrs=['bold']))        
        

if __name__ == "__main__":
    
    # REMOVE
    # log_dir = os.path.join(os.getcwd(), "Logs/")
    # log_file_prefix = os.path.basename(__file__)[:-3]
    # db = meraki.DashboardAPI(
    #     api_key,
    #     wait_on_rate_limit=True,
    #     maximum_retries=25,
    #     output_log=True,
    #     log_path=log_dir,
    #     log_file_prefix=log_file_prefix + "_meraki",
    #     print_console=False,
    # )
    # level = logging.INFO
    # format   = '%(message)s'
    # log_file = f'{log_dir}{log_file_prefix}_log__{datetime.now():%Y-%m-%d_%H-%M-%S}.log'
    # handlers = [logging.FileHandler(log_file), logging.StreamHandler()]
    # logging.basicConfig(level = level, format = format, handlers = handlers)
    # print(colored('This text will be printed in bold and blue color', 'blue', attrs=['bold']))
    # print(Fore.BLUE + f'\033[1m----------------------------------------------------\033[1m')
    # print(Fore.BLUE + f'\033[1mSTEP 1 - GATHER INPUT AND READ CONFIG FILES\033[1m')
    # print(Fore.BLUE + f'\033[1m----------------------------------------------------\033[1m')
    # print(Style.RESET_ALL)
    # REMOVE
    api_key = os.environ.get('MERAKI_DASHBOARD_API_KEY')
    print(border)
    print(colored('STEP 1 - GATHER INPUT AND READ CONFIG FILES', 'blue', attrs=['bold']))
    print(border)
    print("1. Reading API Key for the Meraki dashboard account from the environment variable...")
    masked_key = api_key[-4:].rjust(len(api_key), '*')
    print(f'   Masked API Key: {masked_key}')
    print('   In the Meraki Dashboard, click "My Profile" in the top right and scroll down to see the generated API key. Verify the last 4 digits match the masked API key printed above.')
    choice = input("   Does the last 4 digits match (Y/N):")
    if choice in ["Y","y"]:
        valid_sites = ["1","2","3","4","5"]
        print("2. Let's start configuring your first Meraki network. You would need to input your Pod number to continue.")
        # print("   Enter the Pod number number you selected in WIL Assistant. Check the documentation to determine the Pod number assigned for your session.")
        site_num = input("   Enter the Pod number that you selected in WIL Assistant: ")
        if site_num in valid_sites:
            main(api_key, site_num)
        else:
            print(colored("   ERROR: Check your Pod number again and enter a valid 1 digit Pod number!", 'red', attrs=['bold']))
    elif choice in ["N","n"]:
        print(colored("   ERROR: You have confirmed that the API key does not match the Meraki dashboard. Please contact your lab administrator for further assistance.", 'red', attrs=['bold']))
    else:
        print(colored("   ERROR: Enter a valid choice 'Y' or 'N'!", 'red', attrs=['bold']))
        
