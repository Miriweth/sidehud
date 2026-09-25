# Plugin spec

Everything a game integration for sidehud has to do. It is written to be handed
to someone, or to a code assistant, who has not read the rest of the code.

An integration has two parts, and both are optional:

1. A sender that runs on the gaming PC next to the game: a mod, or a script
   that reads a telemetry feed, a log or a save file. It pushes UDP packets to
   sidehud while the game runs.
2. A panel module, one JavaScript file in `sidehud/static/games/`, that draws
   the game's own numbers on the phone.

Positions need only the sender, the map tile works for every game. The panel
is for everything else: clock, money, health, quest state.

The reference is Stardew Valley: `games/stardew/` is the sender (a SMAPI mod in
C#), `sidehud/static/games/stardew.js` the panel, and `examples/stardew_fake.py`
sends the same packets without the game.

## Where the data may come from

Only from interfaces the game offers for this purpose: a modding API, a
telemetry SDK, a log or save file, an official web API. A sender must not read
or write another process's memory, inject code into a game, or run alongside
anti-cheat. sidehud is for single-player and co-op games and has no place in
competitive online games. Integrations that break these rules are not accepted
into this repository.

## Transport

- UDP to `127.0.0.1:8766`. The port is `map_port` in
  `~/.config/sidehud/config.toml`. sidehud listens on localhost only, so the
  sender has to run on the same PC.
- One JSON object per datagram, UTF-8. Nothing comes back. A datagram that is
  not a JSON object is dropped without a message.
- Keep a datagram under 8 KB. UDP on localhost allows about 64 KB, but a small
  packet costs the game less time to build.
- Send 5 to 20 packets a second while the player is in the game, 10 is a good
  default. Stop sending on menus and title screens.
- sidehud treats the game as running for 3 seconds after the last packet. Then
  the map tile and the game panel disappear.

## Packet

Send the complete state in every packet: `game`, `stats`, `map` and the full
entity list. sidehud keeps only the latest packet, there is no merging.

```json
{
  "game": "stardew",
  "source": "smapi",
  "map": {
    "id": "stardew/Farm",
    "name": "Sunflower Farm",
    "image": "stardew/Farm.png",
    "origin_px": [0, 0],
    "px_per_unit": [16, 16]
  },
  "entities": [
    {"id": "player", "kind": "player", "x": 64.5, "y": 16.4, "heading": 180, "label": "Alex"},
    {"id": "npc:Abigail", "kind": "ally", "x": 50.0, "y": 30.25, "label": "Abigail"},
    {"id": "monster:0", "kind": "other", "x": 70.1, "y": 40.0, "label": "Green Slime"}
  ],
  "stats": {"day": 12, "season": "spring", "money": 12345, "location": "Sunflower Farm"}
}
```

| Key | Type | Meaning |
|---|---|---|
| `game` | string, `[A-Za-z0-9_-]+` | Selects the panel module `sidehud/static/games/<game>.js`. Leave it out when there is no panel. |
| `source` | string | Free text, shows up in `/api/map`. Useful for debugging. |
| `map` | object, string or null | The map the entities are on, see below. |
| `entities` | array | Every marker to draw, see below. |
| `stats` | object | Anything the panel wants. sidehud passes it through untouched. |

What happens when a key is missing:

- `game` and `stats` are reset. Send them in every packet or the panel goes
  blank.
- `map` keeps its last value.
- `entities` keeps the last list. A packet with `entities` replaces the whole
  list, so a marker that is not in the newest packet is gone.

A single player without panel can use the short form instead of `entities`:

```json
{"map": "castle", "x": 120.5, "y": -40.0, "heading": 90, "label": "me"}
```

### Entities

| Key | Type | Meaning |
|---|---|---|
| `x`, `y` | number, required | Position in world units, the same units the map definition uses. |
| `id` | string | Stable per marker. Defaults to `player`. |
| `kind` | `player`, `ally` or `other` | Drawn white, green or yellow. Anything else is drawn as `other`. Defaults to `player`. |
| `heading` | number | Degrees clockwise, 0 points up the screen. Drawn as a short tick on the marker. |
| `label` | string | Drawn next to the marker. Keep it short. |
| `icon` | string | A picture drawn instead of the dot, inside a ring in the colour of `kind`. Same path rules as a map image. Small pictures work best; the page scales them to about 24 px and keeps pixel art sharp. |

`player` is the local player and the marker the tile can follow. Use `ally` for
co-op partners, companions and friendly characters, `other` for the rest. Keep
the list under 100 markers. `z` is accepted and ignored.

### Map

A map object describes how world units turn into pixels on an image:

| Key | Type | Meaning |
|---|---|---|
| `id` | string | Shown in the tile label when there is no `name`. |
| `name` | string | Shown in the tile label. |
| `image` | string or null | Relative path inside the maps folder, an absolute path on the sidehud server, or an `http(s)` URL. `null` draws a grid. |
| `origin_px` | `[x, y]` | Pixel on the image where world position (0, 0) sits. Default `[0, 0]`. |
| `px_per_unit` | `[x, y]` | Pixels per world unit. A negative value flips that axis. Default `[1, -1]`. |

A marker is drawn at `origin_px + position * px_per_unit`. Image rows count
downwards, so a game whose y axis points up needs a negative y scale. To
calibrate a map, take two positions from the game, find both on the image and
solve for scale and origin.

Without an image the tile draws a grid around the markers, still using
`px_per_unit`, so the axes stay right. `"map": null` gives the same grid with
the default scale.

There are two ways to send a map:

1. Inline, as the object above. This is the easiest way for a sender that
   writes its own images.
2. As a string id. sidehud then reads `<maps folder>/<id>.toml`, which holds the
   same keys. The id must not contain `/` or start with a dot.

```toml
# ~/.config/sidehud/maps/castle.toml
name = "Castle"
image = "castle.png"
origin_px = [512, 512]
px_per_unit = [0.5, -0.5]
```

### Map images

The maps folder is `~/.config/sidehud/maps` (`maps_dir` in the config). Put a
game's images under `<maps folder>/<game>/`, subfolders are fine. sidehud serves
them at `/maps/<path>`, paths outside the folder are refused. PNG and JPEG
work, any size; the phone scales them. A sender may write images there while
the game runs: the Stardew mod draws each location from the game itself.

When a picture changes, give it a new path, for example `farm.png?v=2`. The
page loads the new one in the background and keeps the old one on screen until
it is there. Write the file under a temporary name and rename it when it is
complete, so sidehud never serves half an image.

## Panel module

`sidehud/static/games/<game>.js` is an ES module:

```js
const STRINGS = {
  en: { money: 'Money' },
  de: { money: 'Geld' },
};

let ui = null;

function build(root, s) {
  root.innerHTML = `<div class="kv"><span class="k">${s.money}</span><span class="v money">–</span></div>`;
  return { money: root.querySelector('.money') };
}

export default {
  title: 'My Game',
  render(stats, root, ctx) {
    const s = STRINGS[ctx.lang] || STRINGS.en;
    if (!ui || !ui.money.isConnected) ui = build(root, s);
    ui.money.textContent = stats.money != null ? ctx.f0(stats.money) : '–';
    return { sub: stats.location || '' };
  },
};
```

- `title` is shown in the tile label and in the profile menu.
- `render(stats, root, ctx)` runs on every poll: ten times a second while the
  game sends, once a second while the panel is pinned and nothing arrives. In
  that case `stats` is `{}`, so every field needs a fallback.
- `root` is the tile's content element. All panels share it, so check that your
  nodes are still attached (`isConnected`) and build them again when not.
- Build the DOM once and only change text and styles afterwards.
- Put packet values into the page with `textContent` only. Any local process
  can send packets, so they must never reach `innerHTML`.
- Return `{ sub: '...' }` for the right side of the tile label.
- `ctx` has `f0` and `f1` (number formatters for the page locale, `–` for
  null), `locale`, and `lang`, which is `en` or `de`. Keep the panel's strings
  in the module, in both languages.
- The page's classes fit in: `.value` for a big number, `.kv` with `.k` and `.v`
  for a label and value row, `.meter` with a `.fill` child and `--c` as the
  colour (`.warn` and `.crit` recolour it), `.caption` for small print,
  `.hidden`. Colours come from CSS variables such as `--gpu`, `--cpu`, `--mem`
  and `--net`; `--warn` and `--crit` are for warnings only.

A new module shows up in the profile menu after a page reload, sidehud needs no
restart. `/api/games` lists the modules the menu offers.

## Profiles

The menu at the top of the page picks what the phone shows:

- `auto` shows the map and the panel of whatever game is sending.
- `pc` hides both and shows the PC stats only.
- `<game>` keeps that game's panel on screen even when nothing is sent.

The choice is stored on the phone. `?profile=<value>` in the address overrides
it, so a home screen icon can open straight into one profile.

## Checking a sender

```
curl http://127.0.0.1:8765/api/map
```

returns what sidehud holds right now: `live`, the resolved map (image paths
already under `/maps/`), `game`, `stats` and the entities. `live` turns false
3 seconds after the last packet.

`docs/packet.schema.json` is a JSON Schema of the packet. Any JSON Schema
validator can check a sender's output against it.

A minimal sender in Python:

```python
import json
import socket
import time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
while game_is_running():
    x, y, facing = read_position()
    packet = {
        "game": "mygame",
        "source": "mygame-bridge",
        "map": {"id": "mygame/level1", "name": "Level 1", "image": "mygame/level1.png",
                "origin_px": [0, 0], "px_per_unit": [8, 8]},
        "entities": [{"id": "player", "kind": "player", "x": x, "y": y, "heading": facing}],
        "stats": {"health": 80, "maxHealth": 100},
    }
    sock.sendto(json.dumps(packet).encode(), ("127.0.0.1", 8766))
    time.sleep(0.1)
```

## Checklist for a new game

1. Find an interface the game offers: a mod loader, a telemetry SDK, a log or a
   save file. If there is none, the game gets no integration.
2. Write the sender under `games/<game>/` with its own README: how to build
   and install it, what it sends.
3. Decide the world units and write a map definition, inline or as a `.toml`.
4. Add `sidehud/static/games/<game>.js` if the game has numbers worth showing.
5. Test with `curl http://127.0.0.1:8765/api/map` and on the phone in portrait
   and landscape, in German and English (`?lang=de`, `?lang=en`).
