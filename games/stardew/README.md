# Stardew Valley

SidehudBridge is a SMAPI mod. While a save is loaded it sends the local
player's position, the other farmers, villagers and monsters in the same
location and the day's numbers (clock, date, weather, money, energy, health,
luck, skills, today's birthday and festival) to sidehud over UDP, ten times a
second. Nothing is sent on the title screen. sidehud shows the map tile and the
Stardew panel while packets arrive and hides them when the game stops.

## Install

Needs the .NET SDK (Arch: `sudo pacman -S dotnet-sdk`) and SMAPI installed in
the game folder. Then

```
./build.sh
```

finds the game through Steam's library list, builds the mod and puts it into
`Mods/SidehudBridge` next to the other mods. If the game lives somewhere Steam
does not list, pass the folder:

```
./build.sh "/path/to/Stardew Valley"
```

Without an SDK on the gaming box, build elsewhere and copy the folder
(`manifest.json` and `SidehudBridge.dll`) into `Mods/SidehudBridge` by hand.
The Windows build of the game running under Proton works too, the mod resolves
`~` through Wine.

## Config

`Mods/SidehudBridge/config.json`, written on the first start:

- `Host`, `Port`: where sidehud listens, `127.0.0.1` and `8766`
- `SendsPerSecond`: 10
- `MapsDir`: `$XDG_CONFIG_HOME/sidehud/maps/stardew`; `~` and `$XDG_CONFIG_HOME` (`~/.config` when unset) are expanded
- `MapScale`: 0.25, size of the exported map images, 16 px per tile
- `SendNpcs`, `SendMonsters`: villagers and monsters as markers
- `ExportMaps`: false leaves the tile on the grid

## Maps

The first time you enter a location the mod takes the game's own map
screenshot, the same as the `/mapscreenshot` chat command, at `MapScale` and
moves it from the game's Screenshots folder to `MapsDir/<location>.png`. The
game stalls for a moment while it renders. The packet carries the image path,
so there is no `.toml` to write. Delete a png and it is exported again on the
next visit, for example after the farm layout changed.

The mines, Skull Cavern and the volcano are not exported, their layout changes
every visit; the tile shows a grid there.

## What is sent

Only the local player's current location: yourself, other farmers in the same
place, villagers, monsters, at most 80 markers. Where other players are is not
sent. Everything comes through the SMAPI modding API; the mod does not read
game memory. `examples/stardew_fake.py` at the repository root sends the same
packet without the game and doubles as the key reference.

Errors go to the SMAPI log at trace level so the console stays quiet; look
there if nothing shows up on the phone.
