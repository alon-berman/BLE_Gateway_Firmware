import requests
import os
import argparse
import json

# Base URL
BASE_URL = "https://cdn.emnify.net"

class SimIdNotFoundException(Exception):
    ...

def get_sim_id_for_iccid(auth_token, target_iccid):
    endpoint = "/api/v1/sim"
    url = BASE_URL + endpoint
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

    response = requests.get(url, headers=headers)
    print("iccid:")
    print(target_iccid)    
    # Check for a valid response
    if response.status_code == 200:
        sims = response.json()
        for sim in sims:
            if sim["iccid"] == target_iccid:
                print(sim["id"])
                return sim["id"]
        print("did not find anything")
        raise SimIdNotFoundException
    else:
        print(f"Error {response.status_code}: Could not fetch SIMs")
        print(response.text)
        return None
    
    
# Authenticate and get token
def authenticate():
    endpoint = "/api/v1/authenticate"
    url = BASE_URL + endpoint
    headers = {"Content-Type": "application/json"}


    # Payload for authentication
    payload = {
        "application_token": os.environ.get("EMNIFY_APPLICATION_TOKEN")
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response_data = response.json()

    if "auth_token" in response_data:
        return response_data["auth_token"]
    else:
        print("Error: Could not authenticate")
        print(response.text)
        return None

# Activate SIM using the token
def activate_sim(auth_token, sim_id: str):
    print("activating " + sim_id)
    endpoint = f"/api/v1/sim/{sim_id}"
    url = BASE_URL + endpoint

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }

    # Payload to activate SIM
    payload = {
        "status": {
            "id": 1
        }
    }

    response = requests.patch(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        print("SIM activated successfully!")
        print(response.json())
    else:
        print("Error: Could not activate SIM")
        print(response.text)

if __name__ == "__main__":
    # Using argparse to accept the SIM ID
    # you must set the EMnify user / pass environment variables
    # in order to authenticate yourself.
    parser = argparse.ArgumentParser(description="Activate a SIM using EMnify API.")
    parser.add_argument("sim_iccid", help="SIM ICCID to be activated, e.g. 8988303000008562010")
    args = parser.parse_args()

    # Get authentication token
    token = authenticate()
    
    if token:
        
        sim_id = get_sim_id_for_iccid(token, args.sim_iccid)
        # Activate the SIM
        activate_sim(token, str(sim_id))
