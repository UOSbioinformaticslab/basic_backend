import os
import json
import requests
import sys
from config import SWOOLLER_PASSWORD
# Update this once you verify the URL in your docs
API_URL = "http://localhost:8000/datasets"
TOKEN_URL = "http://127.0.0.1:8000/token"
EXAMPLES_DIR = "../examples"


def get_auth_token():
    """Fetches a fresh token using OAuth2 password flow."""
    payload = {
        "grant_type": "password",
        "username": "skw24@sussex.ac.uk",
        "password": SWOOLLER_PASSWORD,
        "scope": "",
        "client_id": "string",
        "client_secret": "string"
    }

    # Using data=payload sends it as application/x-www-form-urlencoded
    response = requests.post(TOKEN_URL, data=payload)

    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Failed to authenticate. Status: {response.status_code}")
        print(response.text)
        sys.exit(1)


def process_examples_directory(directory_path, token):
    if not os.path.exists(directory_path):
        print(f"Error: The directory '{directory_path}' does not exist.")
        return

    json_files = [f for f in os.listdir(directory_path) if f.endswith('.json')]

    if not json_files:
        print(f"No JSON files found in '{directory_path}'.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    for filename in json_files:
        filepath = os.path.join(directory_path, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                dataset_payload = json.load(file)
            dataset_payload["team_id"] = 1
            response = requests.post(API_URL, json=dataset_payload, headers=headers)

            if response.status_code in [200, 201]:
                print(f"Success: {filename} added to the database.")
            else:
                print(f"Failure: Could not add {filename}. Status: {response.status_code}")
                print(f"Response: {response.text}")

        except json.JSONDecodeError:
            print(f"Error: {filename} contains invalid JSON and was skipped.")
        except requests.exceptions.RequestException as e:
            print(f"Connection Error while processing {filename}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred with {filename}: {e}")


if __name__ == "__main__":
    target_dir = EXAMPLES_DIR
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]

    fresh_token = get_auth_token()
    print("Authentication successful. Processing files.")
    process_examples_directory(target_dir, fresh_token)