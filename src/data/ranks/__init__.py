import json
import os
from pprint import pprint

# Get the directory where this file is located
dir_path = os.path.dirname(os.path.realpath(__file__))

def get_files_from_path(path: str='.', extension: str=None) -> list:
    """return list of files from path"""
    result = {}
    def walk_directory(path):
        for subdir, dirs, filenames in os.walk(path):
            for filename in filenames:
                filepath = subdir + os.sep + filename
                if extension == None:
                    result[filename.removesuffix('.json')] = filepath
                elif filename.lower().endswith(extension.lower()):
                    result[filename.removesuffix('.json')] = filepath
            for dirname in dirs:
                if dirname.startswith("__"):
                    pass
                else:
                    walk_directory(path=os.path.realpath(dirname))
    walk_directory(path)
    return result

filelist = get_files_from_path(path=dir_path, extension='.json')

ranks = {}

for _, filepath in filelist.items():
    with open(filepath) as infile:
        rank_data = (json.load(infile))
        identifier = rank_data['description']['identifier']
        ranks[identifier] = rank_data
