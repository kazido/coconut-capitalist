import json
import os

# Get the directory that this file is located in
dir_path = os.path.dirname(os.path.realpath(__file__))


def get_pet_data(pet_ID):
    # Load the JSON data for the given pet name
    file_path = os.path.join(dir_path, f"{pet_ID}.json")
    with open(file_path, "r") as f:
        data = json.load(f)
    
    return data