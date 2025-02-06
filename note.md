with some slight caveats
bot.close() will power off your bot safely, which is important rather than just crashing out to keep discord happy
if bot.close() is slow (test it!) then that's the source of your issue. if it isn't, then it's the ctrl-c handler
if you don't care about a clean exit and just want to quit now, exit(1) on a command will fix things up
the execl stuff is for when you want a restart command
Mine's just !rs
close stuff down, mark the restart as intended (to catch... a particularly annoying error..) and then come back up on it's own
takes like.. 6-7 seconds mostly because it does a lot on startup


### the spot in the discord chat
https://discord.com/channels/267624335836053506/267624335836053506/1165787560170229832




# Items
Items all share some similar attributes
INFORMATIONAL ATTRIBUTES
- name
- display_name
- description
- rarity 
    - every item should have a rarity
- wiki? 
    - maybe, this would be a decent amount of work depending on what wiki means, but could be helpful
- emoji 
    - can be null, but most items will have some emoji to represent them. either custom, or default emoji
- item type
    - can be: key_item, material, tool, crop, seed, pet_item
    - I don't think this will actually effect anything, it will just show up under the wiki
FUNCTIONAL ATTRIBUTES
- sell price 
    - every item can either be sold for a price or cannot be sold. 0 means can't be sold, 1 is mininum

> NOTE: I am not including price, because I don't think that every item can be bought. I think that when I create shops, I can add items into those shops manually, since shops aren't necessarily something that should be dynamically coded (besides maybe rotating shops.) With this in mind, I will manually set the prices of items when I create shops. For rotating shops, I will consider adding a price attribute to the items which I know will be in the rotating shop.

