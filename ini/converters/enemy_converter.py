import configparser


class EnemyConverter:
    @staticmethod
    def from_ini(file_path):
        config = configparser.ConfigParser()
        config.read(file_path)

        enemies = []
        for section in config.sections():
            name = section
            health = config[section].get("health", 0)
            attack = config[section].get("attack", 0)
            shield = config[section].get("shield", 0)

        return enemies


if __name__ == "__main__":
    converter = EnemyConverter()
    enemies = converter.from_ini("ini/enemies.ini")
    for enemy in enemies:
        print(enemy)
