# Item Documentation
## Components
### Required Components

***
`display_name` _str_
>The formatted name of the item.

`unique` _bool_
>If True, the user can only hold one of this item.

`rarity` _str_
>The level of rarity of the item. _(See rarities)_

### Additional Components
***
`tool_tip`
> Add if the item should have a tooltip / description.
> * `value` _str_ - The description of the item.

`purchaseable`
> Enables the item to be bought.
> * `price` _int_ - The price to purchase the item. _Setting the price to 0 will make the item free._
> * `items` _[str]_ (Optional) - List of items to trade in exchange for the item.

`sellable`
> Enables the item to be sold.
> * `price` _int_ - The amount that the item will sell for.

`is_crafted`
> Enables the item to be crafted from different items.
> 
> * `components` _[str]_ - List of items required to make the item.
> * `station` _Station_ - The station that is required to craft the item.

`level_requirement`
> Adds specific level requirements to the item, disabling it from use until the level has been met.
> * `level` _int_ - The level required to use the item.
> * `skill` _Skill_ (Optional) -  The skill that the level requirement will need to be met in. _If no skill is supplied, it will default to the player's overall level._

`area_requirement`
> Adds a requirement that disables the item from being used until a certain area has been unlocked.
> * `area_id` _int_ - The ID of the area that will be required.
> * `exclusive` _bool_ (Optional) - If True, prevents the player from using the item outside of the specified area.
