from dataclasses import dataclass, field


@dataclass(frozen=True)
class ItemInstance:
    """A unique object owned by a player. Use cococap.services.equipment for its effective stats."""

    id: int
    owner_id: int
    template_id: str
    rolled: dict[str, float] = field(default_factory=dict)
    enchants: dict[str, int] = field(default_factory=dict)
