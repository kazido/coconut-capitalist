# Game Data Documentation
### Description
Required. The description category is used to identify the object.

`identifier` _str_
>The identifer of the item. Cannot contain spaces or capitals. This will be used when referencing an item to access its related data. Ex: apple_seed

`type` _str_
>Currently, the only functionality this provides is to assist in sorting a user's inventory and shop candidates. Examples: `item`, `area`, `pet`, etc.

`tags` _[str]_
>Provides further classification. Examples: `seed`, `crop`, `tool`, `weapon`, etc.
***
## Items
### Components

`display_name` _str_
>The formatted name of the item.

`description` _str_
>Description of the item.

`rarity` _str_
>The level of rarity of the item.
* common
* uncommon
* rare
* super_rare
* legendary
* premium

`emoji` _:str:_
>Emoji to represent the item.

`unique` _bool_
>If True, the user can only hold one of this item.

`single_use` _bool_
> If True, the item will disappear from the user's inventory upon use.

`purchaseable`
> Enables the item to be bought.
> * `price` _int_ - The price to purchase the item. _Setting the price to 0 will make the item free._
> * `items` _[str]_ (Optional) - List of items to trade in exchange for the item.

`sellable`
> Enables the item to be sold.
> * `price` _int_ - The amount that the item will sell for.

`level_requirement`
> Adds specific level requirements to the item, disabling it from being purchased or used until the level has been met.
> * `level` _int_ - The level required to use the item.
> * `skill` _str_ (Optional) -  The skill ID that the level requirement will need to be met in. _If no skill is supplied, it will default to the player's overall level._

`area_requirement`
> Adds a requirement that disables the item from being purchased or used until a certain area has been unlocked.
> * `area_id` _int_ - The ID of the area that will be required.
> * `exclusive` _bool_ (Optional) - If True, prevents the player from using the item outside of the specified area. Defaults to False.

`is_crafted`
> Enables the item to be crafted from different items.
> 
> * `components` _[str]_ - List of items required to make the item.
> * `station` _str_ - The station ID that is required to craft the item.

`drop_info`
> Determines the amount and rate at which the material will drop
> * `drop_rate` _int_ - Number of iterations on average for material to drop (Will be set as 1/drop_rate)
> * `minimum` _int_ - Lowest amount of the material that will drop
> * `maximum` _int_ - Highest amount of the material that will drop

`pet_xp` _int_ **(Crops only)**
> Amount of xp to give to pets when consumed.

`harvest_level` **(Crops only)**
> Determines the amount that will be harvested.
> * `minimum` _int_ - Lowest amount of crops that can be harvested.
> * `maximum` _int_ - Highest amount of crops that can be harvested.

`grows_from` _str_ **(Crops only)**
> ID of the seed that the crop grows from.

`growth_odds` _int_ **(Seeds only)**
> umber of iterations on average for material to drop (Will be set as 1/growth_odds)

`grows_into` _str_ **(Seeds only)**
> ID of the crop that the seed will grow into.

`used_to_craft` _[str]_ **(Materials only)**
> List of items that can be crafted with this material
***

## Pets
Pets are placed into folders depending on their rarity. These rarities all have a `_stats.json` file that determines the base stats of each pet in that rarity. These can be overridden using components below.
### Components
`display_name` _str_
>The formatted name of the pet.

`description` _str_
>Description of the pet.

`rarity` _str_
>The level of rarity of the pet.
* common
* uncommon
* rare
* super_rare
* legendary
* premium

`emoji` _:str:_
> Emoji that will represent the pet in the pet module. 

`max_level` _int_ (Optional)
> The maximum level the pet can reach. Based on rarity, but can be overridden.

`price` _int_ (Optional)
> The price the pet can be bought for in bits. Based on rarity, but can be overridden. 

`bonuses` (Optional)
> Bonuses that the pet will apply to different commands. Based on rarity, but can be overridden.
> * `work` _float_ - Percent of work that will be added as a bonus. 
> * `daily` _int_ - The amount of bonus tokens a pet will add to the **/daily** command.

***
## Areas
Current list of areas
* Hub
* Slime Hill
* Rust Belt
* Atmosphere
* Cairo Valley
* Cadrega City
* The Void
### Components
`display_name` _str_
>The formatted name of the area.

`description` _str_
>Description of the area.

`difficulty` _str_
>The difficulty of the area. _(1-10 stars)_  Note, this does not affect the actual difficulty of the area.

`bonus_tokens` _int_
> Amount of extra tokens the players who have unlocked this area will recieve from **/daily**.

`fuel_requirement`
> Adds a fuel requirement to the area, preventing it from being accessed unless the proper fuel is being used in the player's vehicle.
> * `fuel_type` _str_ - The reference name of the Vehicle Fuel required to reach the area.

`level_requirement`
> Adds a level requirement to the area, preventing it from being accessed unless the player has reached the specified level in the specified skill.
> * `level` _int_ - The level required to access the area.
> * `skill` _str_ (Optional) -  The reference name of the skill that the level requirement will need to be met in. _If no skill is supplied, it will default to the player's overall level._ _If "all" is passed as the reference name, all skills must be at the specified level to pass the requirement._