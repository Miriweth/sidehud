# Plugin spec

How a game gets onto the sidehud screen. This file is meant to be handed to a
person or a code assistant who has never seen the rest of the repository; it
has everything needed to write a working integration.

sidehud is a small Python server on a Linux gaming PC. A phone on the same
network shows its web page: PC stats, a minimap and one panel per game. A game
integration feeds the minimap and the panel.

An integration has two parts, both optional:

1. A sender runs on the gaming PC next to the game. It is a mod, a plugin,
   or a script that reads a telemetry feed, a log or a save file, and it sends
   UDP packets to sidehud while the game runs.
2. A panel module is one JavaScript file in `sidehud/static/games/`. It draws
   the game's own numbers on the phone: clock, money, health, quest state.

Positions alone need only the sender, the map tile works for every game. The
reference integration is Stardew Valley: `games/stardew/` (SMAPI mod in C#),
`sidehud/static/games/stardew.js` (panel), `examples/stardew_fake.py` (the
same packets without the game).

## Summary for implementers

A sender must:

1. Send UDP datagrams to `127.0.0.1:8766`, from the same PC.
2. Put one JSON object in each datagram, UTF-8, with finite numbers only.
3. Send about 10 packets a second while the player is in the game, and stop
   on menus and title screens.
4. Put the complete state into every packet: `game`, `stats`, `map` and the
   full `entities` list.
5. Give every entity numeric `x` and `y` in the units of its map.
6. Keep a packet under 8 KB.
7. Write images into the maps folder under a temporary name and rename them
   when complete, and change the image path (`?v=`) whenever a picture changes.
8. Take its data only from interfaces the game offers for it (next section).

A panel module must:

1. Live at `sidehud/static/games/<game>.js`, where `<game>` is the `game` value
   of the packets.
2. `export default { title, render(stats, root, ctx) }`.
3. Build its DOM once, update text afterwards, and put packet values into the
   page with `textContent` only.
4. Cope with `stats` being `{}` or missing any key.

## Where the data may come from

A modding API, a telemetry SDK, a log or save file, an official web API, or
the game's own memory. A sender may read another process's memory, and it may
run inside the game as an injected or proxy DLL when that is the only way at
the data; that is how games without any mod support get a minimap. sidehud is
for single-player and co-op games and has no place in competitive online games
or games with anti-cheat, where a memory reader or an injected DLL gets
accounts banned. The `memreader-py` template in
[re-env](https://github.com/Miriweth/re-env) is a sender of that kind.

## How data moves

```
game ──(mod API, telemetry, log)──> sender ──UDP JSON──> sidehud :8766
                                                            │ keeps the newest packet
phone <──HTTP :8765── page polls /api/map ──────────────────┘
                      and loads static/games/<game>.js for the panel
```

sidehud keeps only the newest packet. There is no history and no merging
between packets, except that `map` and `entities` stay when a packet leaves
them out (see below).

Timing:

| What | Value |
|---|---|
| Map tile and panel stay visible after the last packet | 3 s |
| Markers are dropped after the last packet | 9 s |
| The page asks for new data | every 100 ms while packets arrive, every 1 s otherwise |
| Useful send rate | 5 to 10 packets a second; more is not drawn |

Limits:

| What | Limit |
|---|---|
| Datagram | about 64 KB hard limit, keep it under 8 KB |
| Markers | no hard limit, keep it under 100; the JSON Schema allows 200 |
| Icons | any size; drawn 24 px high, 30 px for the player |
| Map image | any size; keep each side under about 4096 px for older phones |

## Transport

- UDP to `127.0.0.1:8766`. The port is `map_port` in
  `~/.config/sidehud/config.toml`; make it configurable in your sender.
  sidehud listens on localhost only, so the sender runs on the same PC. Games
  under Wine or Proton share the host network, `127.0.0.1` works there too.
- One JSON object per datagram, UTF-8. `NaN` and `Infinity` are not JSON; send
  finite numbers.
- Nothing comes back. A datagram that is not a JSON object is dropped without
  any message, so check what arrived with `/api/map` (see "Checking a sender").
- sidehud may not be running. A sender must not fail or block when nobody
  listens. With a connected UDP socket the operating system reports "connection
  refused" on a later send; ignore that error and keep sending.
- Round positions to two decimals, it keeps packets small.

Sending from a few languages:

```python
import json, socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(json.dumps(packet).encode(), ("127.0.0.1", 8766))
```

```csharp
// .NET 6 or newer (SMAPI, BepInEx on .NET, Godot C#); older Mono needs its own JSON library
var udp = new System.Net.Sockets.UdpClient();
udp.Connect("127.0.0.1", 8766);
byte[] data = System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(packet);
try { udp.Send(data, data.Length); } catch (System.Net.Sockets.SocketException) { }
```

```js
// Node.js
const sock = require('node:dgram').createSocket('udp4');
sock.send(JSON.stringify(packet), 8766, '127.0.0.1');
```

```lua
-- LuaSocket, where the game's Lua has it
local socket = require("socket")
local udp = socket.udp()
udp:sendto(json_string, "127.0.0.1", 8766)
```

### Games without network access

Some mod APIs can write files but not open sockets. Write one JSON object per
line to a file and let this relay forward the lines. Start a new file for every
game session so it does not grow forever.

```python
#!/usr/bin/env python3
"""Forwards JSON lines appended to a file to sidehud: relay.py <file> [port]"""
import socket
import sys
import time

path = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8766
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
with open(path, "a+") as f:
    f.seek(0, 2)  # only new lines, the old ones are stale
    buf = ""
    while True:
        chunk = f.readline()
        if not chunk:
            time.sleep(0.05)
            continue
        buf += chunk
        if not buf.endswith("\n"):
            continue  # the game is still writing this line
        line, buf = buf.strip(), ""
        if line:
            sock.sendto(line.encode(), ("127.0.0.1", port))
```

## Packet

```json
{
  "game": "stardew",
  "source": "smapi",
  "map": {
    "id": "stardew/Farm",
    "name": "Sunflower Farm",
    "image": "stardew/Save_123/Farm.png?v=17",
    "origin_px": [0, 0],
    "px_per_unit": [16, 16]
  },
  "entities": [
    {"id": "player", "kind": "player", "x": 64.5, "y": 16.4, "heading": 180, "label": "Alex", "icon": "stardew/icons/farmer_1.png"},
    {"id": "npc:Abigail", "kind": "ally", "x": 50.0, "y": 30.25, "label": "Abigail"},
    {"id": "monster:0", "kind": "other", "x": 70.1, "y": 40.0, "label": "Green Slime"}
  ],
  "stats": {"day": 12, "season": "spring", "money": 12345, "location": "Sunflower Farm"}
}
```

| Key | Type | Meaning |
|---|---|---|
| `game` | string, `[A-Za-z0-9_-]+` | Selects the panel module `sidehud/static/games/<game>.js`. Leave it out when there is no panel. |
| `source` | string | Free text shown in `/api/map`, for debugging. |
| `map` | object, string or null | The map the entities are on, see "Maps". |
| `entities` | array | Every marker to draw, see "Entities". |
| `stats` | object | Whatever the panel needs. sidehud passes it on untouched. |

How sidehud treats each key:

- `game` must be a string and `stats` an object; anything else counts as
  missing. Both are reset by every packet, so a packet without them clears the
  panel.
- `map` is taken when it is an object, a string or `null`. A packet without
  `map` keeps the previous one.
- `entities` replaces the whole marker list. A marker missing from the newest
  packet is gone. A packet without `entities` keeps the previous list, so
  `"entities": []` is how to clear it.
- Entries of `entities` that are not objects, or that lack `x` or `y`, are
  skipped. sidehud does not check the types of the values; wrong types make the
  marker disappear on the phone.
- Any other key is ignored.

A single marker can use the short form, without `entities`:

```json
{"map": "castle", "x": 120.5, "y": -40.0, "heading": 90, "label": "me"}
```

It becomes one entity with `id` and `kind` set to `player`. The short form
knows `id`, `kind`, `x`, `y`, `z`, `heading`, `label` and `icon`.

## Entities

| Key | Type | Meaning |
|---|---|---|
| `x`, `y` | number, required | Position in world units, the units the map uses. |
| `id` | string | Stable name of the marker. Defaults to `player`. |
| `kind` | `player`, `ally` or `other` | Colour of the marker: white, green or yellow. Anything else is drawn as `other`. Defaults to `player`. |
| `heading` | number | Direction in degrees, clockwise, 0 is up on the screen. Drawn as a short tick on the marker. |
| `label` | string | Drawn to the right of the marker in 12 px text. Keep it short. |
| `icon` | string | Picture drawn instead of the dot, inside a ring in the colour of `kind`. Same path rules as a map image. |

`player` is the local player. In the two follow views the tile centres on the
first `player` entity, or on the first entity when there is none. The player
is drawn last, on top of the others. Use `ally` for co-op partners, companions
and friendly characters and `other` for the rest. `z` is accepted and not used.

Icons are drawn 24 px high (30 px for the player) with their aspect ratio and
without smoothing, so small pixel art stays sharp. PNG with a transparent
background works best. A marker without a loadable icon is drawn as a dot.

Converting a game's direction to `heading`:

| The game gives | `heading` |
|---|---|
| Yaw in degrees, 0 = north, clockwise | `yaw` |
| Yaw in degrees, 0 = north, counter-clockwise | `(360 - yaw) % 360` |
| Math angle `a` in radians, 0 = east, counter-clockwise, y up | `(90 - degrees(a)) % 360` |
| Angle in degrees, 0 = east, clockwise, y down | `(a + 90) % 360` |
| Facing 0 up, 1 right, 2 down, 3 left | `facing * 90` |
| Direction vector `(dx, dy)` with y pointing down the screen | `degrees(atan2(dx, -dy)) % 360` |

"Up", "north" and "down" mean the directions on the map image. In JavaScript
`%` keeps the sign, use `((h % 360) + 360) % 360` there.

## Maps

A map says how world units become pixels on an image:

| Key | Type | Meaning |
|---|---|---|
| `id` | string | Shown in the tile label when there is no `name`. |
| `name` | string | Shown in the tile label. |
| `image` | string or null | Path inside the maps folder, an absolute path on the sidehud server, or an `http(s)` URL. `null` or missing draws a grid. |
| `origin_px` | `[x, y]` | Pixel on the image where world position (0, 0) is. Default `[0, 0]`. |
| `px_per_unit` | `[x, y]` | Image pixels per world unit. A negative value flips the axis. Default `[1, -1]`. |

A marker lands on pixel `origin_px + position * px_per_unit`, per axis. Image
rows count downwards, so a game whose y axis points up needs a negative y
scale, and a game that uses screen or tile coordinates with y down uses a
positive one. Rotated maps are not supported.

If the image is a crop of the world, `origin_px` is the pixel of world (0, 0)
relative to the crop, which can be negative. Example: an image that starts at
world pixel (640, 320) and is scaled to a quarter has
`origin_px = [-160, -80]` and `px_per_unit = [0.25, 0.25]` for positions in
world pixels.

To calibrate a map, take two positions from the game that are far apart and
find them on the image. Say world (100, 50) is pixel (412, 188) and world
(300, -150) is pixel (812, 588):

```
px_per_unit x = (812 - 412) / (300 - 100)  =  2
px_per_unit y = (588 - 188) / (-150 - 50)  = -2
origin_px x   = 412 - 100 * 2              = 212
origin_px y   = 188 - 50 * (-2)            = 288
```

Without an image the tile draws a grid around the markers, still with
`px_per_unit`, so directions stay right. The grid needs at least one marker.

A map can be sent in two ways:

1. Inline as an object, as in the packet above. Best for senders that write
   their own images.
2. As a string id. sidehud reads `<maps folder>/<id>.toml`, which holds the
   same keys. The id must not contain `/` or start with a dot. A missing or
   broken file gives no map, and the tile shows the grid.

```toml
# ~/.config/sidehud/maps/castle.toml
name = "Castle"
image = "castle.png"
origin_px = [512, 512]
px_per_unit = [0.5, -0.5]
```

## Images

Map images and icons live in the maps folder, `~/.config/sidehud/maps` by
default (`$XDG_CONFIG_HOME/sidehud/maps` when that variable is set, or
`maps_dir` in the config). Put a game's files under `<maps folder>/<game>/`,
subfolders are fine. sidehud serves them at `/maps/<path>` and refuses paths
outside the folder. A relative `image` or `icon` in a packet is a path inside
that folder: `stardew/icons/farmer_1.png` becomes `/maps/stardew/icons/farmer_1.png`.

A sender can write images there while the game runs:

- Write to a temporary name in the same folder and rename it when the file is
  complete. sidehud might otherwise serve half a file.
- When a picture changes, change its path, for example `farm.png?v=18`. The
  page loads the new picture in the background and keeps the old one on screen
  until it is there. Without a new path the phone keeps showing the old one.
- The phone does not retry a picture that failed to load. Send an icon or
  image path only after the file exists, or change `?v=` when it appears.
- A Windows game under Wine or Proton sees the Linux file system as drive
  `Z:`, so the maps folder is `Z:\home\<user>\.config\sidehud\maps` there.

PNG and JPEG work. The Stardew mod draws its maps at a quarter of the game's
resolution, 16 px per tile, which keeps a farm around 1.5 MB.

## Panel module

`sidehud/static/games/<game>.js`, an ES module. A complete example:

```js
const STRINGS = {
  en: { health: 'Health', gold: 'Gold' },
  de: { health: 'Gesundheit', gold: 'Gold' },
};

let ui = null;

function build(root, s) {
  root.innerHTML = `
    <div class="kv"><span class="k">${s.health}</span><span class="v health">–</span></div>
    <div class="meter" style="--c:var(--mem)"><div class="fill"></div></div>
    <div class="kv"><span class="k">${s.gold}</span><span class="v gold">–</span></div>`;
  const q = c => root.querySelector('.' + c);
  return { health: q('health'), meter: q('meter'), fill: q('fill'), gold: q('gold') };
}

export default {
  title: 'My Game',
  render(stats, root, ctx) {
    const s = STRINGS[ctx.lang] || STRINGS.en;
    if (!ui || !ui.health.isConnected) ui = build(root, s);
    const hp = stats.health, max = stats.maxHealth;
    const pct = hp != null && max ? Math.max(0, Math.min(100, hp / max * 100)) : 0;
    ui.health.textContent = hp != null ? `${ctx.f0(hp)} / ${ctx.f0(max)}` : '–';
    ui.fill.style.width = pct + '%';
    ui.meter.classList.toggle('crit', hp != null && pct < 30);
    ui.gold.textContent = ctx.f0(stats.gold);
    return { sub: stats.area || '' };
  },
};
```

The contract:

- The file name is the game id. `/api/games` lists every `.js` file in the
  folder and the profile menu offers each module that loads.
- The page imports every module in the folder when it opens, to fill the
  profile menu, and keeps them until it is reloaded. The panel of a module
  appears when a packet names its game or when the user pins it. A module that
  fails to load gives no panel and no error on screen, the browser console has
  the reason.
- `title` is shown in the tile label and in the profile menu.
- `render(stats, root, ctx)` runs ten times a second while packets arrive and
  once a second while the panel is pinned and nothing arrives. In that case
  `stats` is `{}`. Every value needs a fallback.
- `root` is the content element of the tile and is shared by all panels. Keep
  references to your nodes, check `isConnected`, and build again when another
  panel replaced them.
- Build the DOM once and only change text, classes and styles afterwards.
  Static strings of your own may go into `innerHTML`; packet values go through
  `textContent`, because any program on the PC can send packets.
- Return `{ sub: '...' }` to fill the right side of the tile label.
- An exception in `render` is logged to the browser console and the panel
  keeps its last state.
- `ctx.f0(v)` and `ctx.f1(v)` format a number with no and one decimal in the
  page's locale and return `–` for `null` or `undefined`. `ctx.lang` is `en` or
  `de`, `ctx.locale` the matching locale string. Keep the panel's own strings
  in the module, in both languages.
- Available classes: `.value` for a big number (with a `.unit` span), `.kv`
  with `.k` and `.v` for a label and value row, `.meter` with a `.fill` child
  and the colour in `--c` (`.warn` and `.crit` recolour it), `.caption` for small
  text, `.hidden`. Colours are the CSS variables `--gpu`, `--cpu`, `--mem`,
  `--net`, `--ink`, `--ink-2` and `--muted`; `--warn` and `--crit` are for
  warnings only.
- In landscape on a phone the tile is about 240 px wide and 330 px high and
  cuts off what does not fit. Keep a panel to about eight rows.
- Keep it one file with no imports; the page has no build step.

Panel modules live inside the sidehud package. Develop them in a git checkout
started with `python -m sidehud`; the page picks up a changed module on reload.

## Profiles

The menu at the top of the page picks what the phone shows:

- `auto` shows the map and the panel of whichever game is sending.
- `pc` hides both and shows only the PC stats.
- `<game>` keeps that game's panel on screen, even while nothing is sent.

The phone stores the choice. `?profile=<value>` in the address overrides it,
so a home screen icon can open straight into one profile.

## Checking a sender

Send one marker by hand:

```
python3 -c 'import json, socket; socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(json.dumps({"entities": [{"x": 0, "y": 0, "label": "test"}]}).encode(), ("127.0.0.1", 8766))'
```

Then look at what sidehud holds:

```
curl -s http://127.0.0.1:8765/api/map
```

```json
{
  "live": true,
  "age": 0.4,
  "map": null,
  "game": null,
  "stats": null,
  "source": "udp",
  "entities": [{"x": 0, "y": 0, "label": "test", "id": "player", "kind": "player", "seen": 1790380000.2}]
}
```

- `live` is true for 3 seconds after a packet. `age` is the number of seconds
  since the last one, `null` before the first.
- `source` is the packet's `source`, or `udp` when it had none. If `age` does
  not drop back when you send, the datagram was not a JSON object.
- `map` is resolved: a string id is replaced by its `.toml` content, relative
  `image` paths start with `/maps/`. Entity icons are resolved the same way.
- Every entity carries `seen`, the Unix time sidehud got it.

The other endpoints: `/api/games` lists the panel modules, `/maps/<path>`
serves an image from the maps folder (open it in a browser to check a path),
and `/api/stats` has the PC sensors. The page itself is at
`http://<pc>:8765/`; `?lang=en` or `?lang=de` switches the language and
`?profile=<game>` pins your panel.

A complete sender to start from, with a marker walking in a circle, a map
without image and stats for the panel above:

```python
#!/usr/bin/env python3
import json
import math
import socket
import time

SIDEHUD = ("127.0.0.1", 8766)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
start = time.time()
while True:
    t = time.time() - start
    angle = t / 5
    x, y = 20 * math.cos(angle), 20 * math.sin(angle)
    packet = {
        "game": "mygame",
        "source": "mygame-example",
        "map": {"id": "mygame/arena", "name": "Arena", "image": None, "origin_px": [0, 0], "px_per_unit": [8, 8]},
        "entities": [
            {"id": "player", "kind": "player", "x": round(x, 2), "y": round(y, 2),
             "heading": round(math.degrees(angle) + 180) % 360, "label": "me"},
            {"id": "npc:camp", "kind": "ally", "x": 0, "y": 0, "label": "camp"},
        ],
        "stats": {"health": 80 + round(20 * math.sin(t)), "maxHealth": 100, "gold": int(t) * 3, "area": "Arena"},
    }
    try:
        sock.sendto(json.dumps(packet).encode(), SIDEHUD)
    except OSError:
        pass  # sidehud is not running, try again with the next packet
    time.sleep(0.1)
```

`docs/packet.schema.json` is a JSON Schema of the packet; any validator for
JSON Schema draft 2020-12 can check a sender's output against it.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No map tile | No valid packet arrived: wrong port, sent to the LAN address instead of `127.0.0.1`, not a JSON object, or the profile is set to PC only. Check `age` in `/api/map`. |
| Map tile with a grid instead of the image | `image` is missing or wrong. Open `/maps/<path>` in a browser; for a string id check `<maps folder>/<id>.toml`. |
| Markers shifted or mirrored | Wrong `origin_px`, `px_per_unit` or sign of the y scale, or positions in other units than the calibration. Calibrate with two points far apart. |
| Markers from the previous area stay | The packet has no `entities` key. Send the full list every time, `[]` when empty. |
| Old picture after the game changed | The image path did not change. Add or bump `?v=`. |
| Icon shown as a dot | The icon path is wrong, or the phone asked before the file existed. Change `?v=` after writing it. |
| No panel | `game` does not match the file name, the module has a syntax error, or it has no default export with `title` and `render`. See the browser console. |
| Panel flickers or loses input | The module rebuilds its DOM on every call. |
| Panel shows dashes | `stats` keys differ from what the module reads, or the panel is pinned and nothing is sent. |
