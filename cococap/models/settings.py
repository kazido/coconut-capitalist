from pydantic import BaseModel


class Settings(BaseModel):
    auto_deposit: bool = False
    # More to come
