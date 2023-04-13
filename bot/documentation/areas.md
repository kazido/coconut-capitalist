# Areas Documentation
## Areas
* Hub
* Slime Hill
* Rust Belt
* Atmosphere
* Cairo Valley
* Cadrega City
* The Void

## Components
### Required Components
---
`display_name` _str_ 
> The display name of the area.

`difficulty` _int_
> Rating in stars in difficulty of the area. _This is purely for informational purposes_.

`description` _str_
> Description of the area that will be displayed under the area name on the list of areas.

### Additional Components
---
`bonus_tokens` _int_
> Amount of extra tokens the players who have unlocked this area will recieve from **/daily**.

`fuel_requirement`
> Adds a fuel requirement to the area, preventing it from being accessed unless the proper fuel is being used in the player's vehicle.
> * `fuel_type` _str_ - The reference name of the Vehicle Fuel required to reach the area.

`level_requirement`
> Adds a level requirement to the area, preventing it from being accessed unless the player has reached the specified level in the specified skill.
> * `level` _int_ - The level required to access the area.
> * `skill` _str_ (Optional) -  The reference name of the skill that the level requirement will need to be met in. _If no skill is supplied, it will default to the player's overall level._ _If "all" is passed as the reference name, all skills must be at the specified level to pass the requirement._