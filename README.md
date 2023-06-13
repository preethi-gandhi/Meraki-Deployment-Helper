# CLUS23-LABDEV1100
Meraki Network Deployment using APIs


Assumptions:
1. Meraki Dashboard account created for your User ID and an Organization has been created in the Meraki Dashboard.
2. Devices and License already claimed into the Organization. Check 'Organization> Inventory'
3. Python 3.10 installed in the jump server where script will be run.
4. API key generated for the account under 'My Profile' page in the Dashboard
5. Script execution environment is already setup with the API Key mapped as an environment variable. Python packages installed in the environment using 'pip3 install -r requirements.txt'
6. Network and Device configs are predefined in yaml files. This will be our source of truth for configuration.

Procedure:
1. Go to the Project directory and create a virtual environment -
    /usr/local/bin/python3 -m venv env

2. Activate the virtual environment -
    source env/bin/activate

3. Install packages in "requirements.txt" - 
    pip3 install -r requirements.txt
 
4. Generate API key for your account in the Meraki Dashboard. Set API Key as an environment variable -
    export MERAKI_DASHBOARD_API_KEY=<aaaaaa>
  
5. Exit the environment and activate the virtual environment again.
  
6. Run the configuration script -
    python3 configuration_CL.py
