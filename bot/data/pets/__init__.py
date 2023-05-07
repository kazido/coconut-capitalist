import json
import os
from pprint import pprint

# Get the directory where this file is located
dir_path = os.path.dirname(os.path.realpath(__file__))


def get_files_from_path(path: str = ".", extension: str = None) -> list:
    """return list of files from path"""
    result = {}
    stats = {}
    for subdir, dirs, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(subdir, filename)
            if filename.startswith("__"):
                pass
            if extension == None:
                result[filename.removesuffix(".json")] = filepath
            elif filename.startswith("_stats"):
                pass
            elif filename.lower().endswith(extension.lower()):
                result[filename.removesuffix(".json")] = filepath
        for dirname in dirs:
            if dirname.startswith("__"):
                pass
            else:
                stats[dirname] = os.path.join(subdir, dirname, "_stats.json")
    return result, stats


pet_files, stat_files = get_files_from_path(path=dir_path, extension=".json")

pets = {}
stats = {}

for identifier, filepath in pet_files.items():
    with open(filepath) as infile:
        pets[identifier] = json.load(infile)

for rarity, filepath in stat_files.items():
    with open(filepath) as infile:
        stats[rarity] = json.load(infile)
