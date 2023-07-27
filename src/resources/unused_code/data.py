
def get_attribute(parent_dict, item_id=None, attribute="components.display_name"):
    """Used to easily get data from an item, rank, entity, etc.

    Args:
        item_id (int): The ID of the item
        attribute (str): The component and subcomponent of the item. Ex: "components.display_name"
        parent_dict (dict): Dict to search for data in

    Returns:
        any: The component requested
    """
    attributes = attribute.split('.')
    if item_id:
        current_value = parent_dict[item_id]
    else:
        current_value = parent_dict
    for attr in attributes:
        if attr in current_value:
            current_value = current_value[attr]
        else:
            return None
    return current_value
