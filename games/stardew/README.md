# Stardew Valley

SidehudBridge is a SMAPI mod. While a save is loaded it sends a live map of
the location you are in, the local player's position, the other farmers,
villagers and monsters there with an icon each, and the day's numbers (clock, date, weather, money, energy, health,
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

SMAPI loads mods when the game starts, so restart the game after a build.

Without an SDK on the gaming box, build elsewhere and copy the folder
(`manifest.json` and `SidehudBridge.dll`) into `Mods/SidehudBridge` by hand.
The Windows build of the game running under Proton works too, the mod resolves
`~` through Wine.

## Config

`Mods/SidehudBridge/config.json`, written on the first start:

- `Host`, `Port`: where sidehud listens, `127.0.0.1` and `8766`
- `SendsPerSecond`: 10
- `MapsDir`: `$XDG_CONFIG_HOME/sidehud/maps/stardew`; `~` and `$XDG_CONFIG_HOME` (`~/.config` when unset) are expanded
- `MapScale`: 0.25, size of the map images, 16 px per tile
- `MapRefreshSeconds`: 10, how often the map of your location is drawn again; 0 draws it only when you arrive
- `SendNpcs`, `SendMonsters`: villagers and monsters as markers
- `SendIcons`: pictures of the characters for the markers
- `ExportMaps`: false leaves the tile on the grid

## Maps

The mod draws the map of your location from the running game, one piece of
2048 pixels per frame, the same way the game's `/mapscreenshot` command does
it but spread out, so the game does not stall. It draws the map again every
`MapRefreshSeconds`, which keeps crops, machines and new buildings current,
and map mods show up because the game draws them. Farmers, villagers and
monsters are left out of the picture, the markers show them. Images go to
`MapsDir/<save>/<location>.png`, one folder per save. The mines, Skull Cavern
and the volcano dungeon share one file per save, a level looks different on
every visit anyway.

The icons are cut from the game's sprites the first time a character shows
up: villagers get the head from the social page, monsters their first
animation frame, farmers the small portrait from the map page. They are stored
in `MapsDir/icons`.

## What is sent

Only the local player's current location: yourself, other farmers in the same
place, villagers, monsters, at most 80 markers. Where other players are is not
sent. Everything comes through the SMAPI modding API; the mod does not read
game memory. `examples/stardew_fake.py` at the repository root sends the same
packet without the game and doubles as the key reference.

Errors go to the SMAPI log at trace level so the console stays quiet; look
there if nothing shows up on the phone.
