<div align="center">

# 🥥 Coconut Capitalist

### An idle-adventure economy game that lives inside Discord

Mine deep, chop trees, reel in giant fish, grow crops, hatch pets and build a coconut empire,
all from one clean menu that never floods your chat.

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-2.7-5865F2?logo=discord&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-SQLAlchemy-003B57?logo=sqlite&logoColor=white)
![Status](https://img.shields.io/badge/status-in%20active%20development-E6B34A)

</div>

---

## ✨ What is it?

**Coconut Capitalist** is a Discord bot that turns your server into a tiny economy. Type `/play` and you get **one
menu** that links to everything: skills, shop, inventory, pets, trading, parties and more. No wall of commands to
learn, and no spam: the menu edits itself as you move around.

Everything you earn is yours to spend, trade, craft and show off. Rare finds get their own spotlight screen, and every
item has a hand-drawn pixel-art icon in a border coloured by its rarity.

## 🎮 Skills

| | Skill | What you do |
|---|---|---|
| ⛏️ | **Mining** | Dig a 30-row shaft one row at a time. Richer ore is harder to dig and builds pressure, so every click is a risk. Find vaults, mini-wyrmholes and glowing reactor gems. Upgrade your **Reactor** and keep a **magnet** fuelled to chase the richest lode. |
| 🌳 | **Foraging** | Chop trees across 20 zones. Every grain wants a different chop style, so learn the patterns and build a streak. Tree **species** change what falls. Help fell a **community tree** or start a **party tree** with friends. |
| 🎣 | **Fishing** | Cast a line, hook the bite and reel it in with a timing mini-game. Chase bosses, crack chests, keep field notes and build your fish records. Land a lucky **double hook** for a second catch. |
| 🌱 | **Farming** | Plant, water and harvest. The weather helps, a daily **market** pays a bonus, and rare deeds unlock more land. |

Every skill has its own **mastery tree** (build your playstyle with points) and a **tool path** that you upgrade from a
rusty starter to a late-game masterwork. Enchant tools with **scrolls** you find along the way.

## 🐾 And everything around it

- 🐾 **Pets**: hatch pets from **Familiar Orbs** in three tiers, feed them, level them and bring them along for bonuses.
- 🛠️ **Workbench**: craft consumables from the things you gather.
- 🌱 **The Releaf Foundation**: players donate rare drops together; when the forest blooms, everyone benefits for a while.
- 📦 **Shipments**: fill crates for bits and xp.
- 🤝 **Trading & parties**: swap items safely, team up for shared trees and boss casts.
- 🏅 **Ranks & leaderboards**: climb 16 ranks, compare with friends, track your records.
- 🎲 **Minigames**: blackjack, high-low and more, when you want to gamble a little.
- 📚 **A built-in wiki and bestiary**: look up any item, fish or rule without leaving Discord.

## 🎨 The look

- **One live menu.** Built on Discord's newest message components, so pages feel like an app, not a chat.
- **Pixel-art everything.** More than 190 item icons in a stone cell whose border changes colour with rarity:

  `Common` ⬜ → `Uncommon` 🟩 → `Rare` 🟦 → `Super Rare` 🟪 → `Legendary` 🟧 → `Premium` 🟥 → `Mythical` 🩷

- **Rare-drop moments.** Super rare finds get a full-screen reveal with the drop rate, and the top rarities gently shine.

## 📸 Screenshots

<!-- Add screenshots to docs/screenshots/ and replace the lines below. -->

| The hub | A mine | The inventory |
|---|---|---|
| _coming soon_ | _coming soon_ | _coming soon_ |

| A rare drop | The pet house | Foraging |
|---|---|---|
| _coming soon_ | _coming soon_ | _coming soon_ |

## 🧰 Built with

- **Python 3.11+** and **discord.py** (modern components, no message-content hacks)
- **SQLite** through SQLAlchemy and Alembic migrations, with atomic updates for every player action
- **TOML game data**: every balance number lives in `configs/`, checked at startup, so tuning never needs a code change
- A typed, tested rules engine: game logic is plain Python with no Discord objects, covered by **1,800+ tests**

## 🚀 Running your own

Want to host it? The setup guide, architecture notes and database tips are in
**[docs/DEVELOPING.md](docs/DEVELOPING.md)**.

## 🙏 Credits

- Game design, code and pixel art: [@kazido](https://github.com/kazido)
- Many item icons are recoloured and reframed from the free
  [Raven Fantasy Icons](https://clockworkraven.itch.io/raven-fantasy-icons) by **Clockwork Raven Studios**.
  Thank you for the beautiful art! Extra icons are hand-drawn to match.

<div align="center">

🥥 _Plant a coconut, build an empire._ 🥥

</div>
