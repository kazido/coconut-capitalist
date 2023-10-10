import peewee

from src.entity_models import BaseModel
from src.item_models import ItemType
from logging import getLogger


log = getLogger(__name__)


class DoesNotExist(Exception):
    pass


class ModelManager:
    """Useful when you have an entity ID and want to retrieve data about said entity."""

    def __init__(self, model):
        self.model: BaseModel = model

    def get(self, entity_id):
        """Retrieve an entity by its ID."""
        try:
            entity: self.model = self.model.get_by_id(entity_id)
            data = {**entity.__data__}
            return data
        except peewee.DoesNotExist:
            raise DoesNotExist(f"No {self.model.__name__} found with ID {entity_id}")

    def set_field(self, entity_id, field, value):
        """Set the field of an entity"""
        if not hasattr(self.model, field):
            raise ValueError(
                f"Field '{field}' does not exist in model {self.model.__name__}"
            )
        updated_rows = self.model.set_by_id(entity_id, {field: value})
        if updated_rows:
            return updated_rows
        raise DoesNotExist(f"No {self.model.__name__} found with ID {entity_id}")

    def get_related(self, entity_id):
        """Retrieve an entity and its related data from a specified extended table."""
        try:
            entity: self.model = self.model.get_by_id(entity_id)
            if not entity.filter_type:
                log.debug("Specified item had no type, returning fields.")
                return self.get(entity_id)
            related_model = ItemType[entity.filter_type].value
            related_entity: related_model = related_model.get_by_id(entity_id)

            combined_data = {**entity.__data__, **related_entity.__data__}
            return combined_data
        except peewee.DoesNotExist:
            raise DoesNotExist(f"No {self.model.__name__} found with ID {entity_id}")

    def get_display_name(self, entity_id):
        """Retrieve the display name or name of the entity."""
        try:
            entity = self.model.get_by_id(entity_id)
            display_name = getattr(entity, "display_name", None)
            name = getattr(entity, "name", None)
            return display_name or name
        except peewee.DoesNotExist:
            raise DoesNotExist(f"No {self.model.__name__} found with ID {entity_id}")


# class ToolManager(ItemManager):
#     def __init__(self, owner_id: int, tool_id: str) -> None:
#         super().__init__(owner_id, tool_id)
#         self._total_power: int

#     @property
#     def total_power(self):
#         self._total_power = self.get_field("power") * self.get_field("star_level")
#         return self._total_power
