import configparser
import os


class _DynamicObject:
    def __init__(self, **attributes):
        for key, value in attributes.items():
            setattr(self, key, value)

    def __repr__(self):
        representation = ""
        for key, value in self.__dict__.items():
            representation += f"{key}: {value}\n"
        return representation.strip()


def fetch(identifier):
    ini_directory = "ini"
    try:
        filename, obj_id = identifier.split(".")
    except ValueError:
        raise ValueError("Identifier must be in the format 'filename.identifier'")

    ini_path = os.path.join(ini_directory, f"{filename}.ini")
    if not os.path.exists(ini_path):
        raise FileNotFoundError(
            f"INI file '{filename}.ini' not found in directory '{ini_directory}'"
        )

    config = configparser.ConfigParser()
    config.read(ini_path)

    if obj_id not in config:
        raise KeyError(f"Identifier '{obj_id}' not found in '{filename}.ini'")

    attributes = {key: value for key, value in config[obj_id].items()}
    return _DynamicObject(**attributes)


if __name__ == "__main__":
    print(fetch("swords.rustedbroadsword"))
