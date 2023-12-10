import pytest
from cococap.user import get_user_data, set_user_field, get_user_related, UserDoesNotExist

def test_get_user():
    # Mock a user ID
    user_id = 326903703422500866
    
    # Call the function
    user_data = get_user_data(user_id)
    
    # Assert that the function returns a user with the expected ID
    assert user_data["user_id"] == user_id


def test_set_user_field():
    # Mock a user ID and field data
    user_id = 12345
    field = "name"
    value = "TestUser"
    
    # Call the function
    set_user_field(user_id, field, value)
    updated_user = get_user_data(user_id)
    
    # Assert that the field was updated
    assert updated_user[field] == value
    
    # Test setting a non-existent field
    with pytest.raises(ValueError):
        set_user_field(user_id, "nonexistent_field", "value")
        
        
def test_get_user_related():
    # Mock a user ID and related table
    user_id = 12345
    related_table = "combat"
    
    # Call the function
    related_data = get_user_related(user_id, related_table)
    
    # Assert that the function returns the expected data
    assert "monsters_slain" in related_data  # replace "combat_data_key" with a key you expect in combat data
    
    # Test retrieving data for a non-existent user
    with pytest.raises(UserDoesNotExist):
        get_user_related(99999, related_table)
