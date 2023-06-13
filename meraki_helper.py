import sys, getopt, requests, json
import os
import meraki
import time
import pandas as pd
import requests

# TZ Lists
HDT = ["HI"]
AKDT = ["AK"]
PDT = ["OR", "WA", "CA", "NV", "BC"]
MDT = ["AZ", "NM", "UT", "CO", "WY", "ID", "MT", "AB"]
CDT = ["TX", "OK", "KS", "NE", "SD", "ND", "MN", "IA", "MO", "AR", "LA", "MS", "AL", "TN", "IL", "WI", "SK", "MB"]
EDT = ["FL", "GA", "SC", "NC", "KY", "WV", "VA", "IN", "MI", "OH", "PA", "NY", "VT", "ME", "NH", "MA", "RI", "CT", "NJ", "DE", "MD", "DC", "ON", "QC", "NB"]
ADT = ["NS", "PE", "NL"]

def timeZone(location):
    # TODO: Meraki module
    if location in HDT:
        the_time_zone = "Pacific/Honolulu"
    elif location in AKDT:
        the_time_zone = "America/Anchorage"
    elif location in PDT:
        the_time_zone = "America/Los_Angeles"
    elif location in MDT:
        the_time_zone = "America/Denver"
    elif location in CDT:
        the_time_zone = "America/Chicago"
    elif location in EDT:
        the_time_zone = "America/New_York"
    elif location in ADT:
        the_time_zone = "America/Halifax"
    return the_time_zone


def get_organizations(m):
    try:
        response = m.organizations.getOrganizations()
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to get Organizations')
        
        
def create_network(m, org, net_name, net_type, net_tags, net_tz):
    try:
        response = m.organizations.createOrganizationNetwork(
                organizationId = org,
                name = net_name,
                productTypes = net_type,
                tags = net_tags,
                timeZone = net_tz 
            )
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to create new network {net_name}')


def get_networks(m, org):
    try:
        response = m.organizations.getOrganizationNetworks(
                organizationId = org)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to get networks in Org {org}')


def delete_network(m, net_id):
    try:
        response = m.networks.deleteNetwork(
                networkId = net_id
            )
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to delete network - {net_id}')
             
                
def claim_devices(m, net_id, serials):
    try:
        response = m.networks.claimNetworkDevices(
                networkId = net_id,
                serials = serials
            )
        return response
    except Exception as e:
        print(e)
        print('ERROR: Unable to claim devices to network')


def configure_device(m, serial, name, tags):
    try:
        response = m.devices.updateDevice(
                serial,
                name = name,
                tags = tags
            )
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure device {serial}')
 
 
def configure_alerts(m, net_id, recipients, alerts):
    try:
        response = m.networks.updateNetworkAlertsSettings(
                networkId = net_id,
                defaultDestinations = recipients,
                alerts = alerts
            )
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure network alerts')
        

def update_network_vlan_settings(m, net_id, vlan_settings):
    try:
        response = m.appliance.updateNetworkApplianceVlansSettings(networkId = net_id,
                                                          vlansEnabled = vlan_settings)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to update appliance vlan settings for the network')
       
            
def create_appliance_vlan(m, net_id, vlan_id, vlan_name, vlan_config):
    try:
        response = m.appliance.createNetworkApplianceVlan(networkId = net_id,
                                                          id = vlan_id,
                                                          name = vlan_name,
                                                          **vlan_config)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure vlan {vlan_name}')
        
        
def configure_appliance_port(m, net_id, port_id, port_config):
    try:
        response = m.appliance.updateNetworkAppliancePort(networkId = net_id,
                                                          portId = port_id,
                                                          **port_config)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure appliance port {port_id}')


def create_appliance_L7FWRules(m, net_id, L7_FW_rules):
    try:
        response = m.appliance.updateNetworkApplianceFirewallL7FirewallRules(networkId = net_id,
                                                          rules = L7_FW_rules)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure appliance L7 FW Rules {L7_FW_rules}')
    
        
def configure_switch_settings(m, net_id, management_vlan):
    try:
        response = m.switch.updateNetworkSwitchSettings(networkId = net_id, vlan = management_vlan)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure switch management vlan to  {management_vlan}')


def configure_ssid(m, net_id, ssid_num, ssid_settings):
    try:
        response = m.wireless.updateNetworkWirelessSsid(net_id, ssid_num, **ssid_settings)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure ssid - {ssid_settings["name"]}')
        
        
def configure_rfprofile(m, net_id, rf_profile_name, band_selection, rf_settings):     
    try:
        response = m.wireless.createNetworkWirelessRfProfile(net_id, rf_profile_name, band_selection, **rf_settings)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to configure RF profile - {rf_profile_name}')


def map_ap_rfprofile(m, ap_serial, ap_rfprofile):
    try:
        response = m.wireless.updateDeviceWirelessRadioSettings(serial = ap_serial, rfProfileId = ap_rfprofile)
        return response
    except Exception as e:
        print(e)
        print(f'ERROR: Unable to map AP {ap_serial} with RF profile {ap_rfprofile}')
           