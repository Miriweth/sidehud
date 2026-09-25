# Minimap

sidehud shows a map tile while something sends positions to its UDP port,
`127.0.0.1:8766` by default. Where the positions come from is your business:
a game mod, a telemetry API, a save-file watcher, a script. The server only
draws.

## Packet format

One JSON object per UDP datagram:

```json
{
  "source": "my-mod",
  "map": "castle",
  "entities": [
    {"id": "me", "kind": "player", "x": 120.5, "y": -40.0, "heading": 90, "label": "me"},
    {"id": "bob", "kind": "ally", "x": 100.0, "y": -35.0}
  ]
}
```

- `map`: id of a map definition (below). Leave it out and you get a plain grid.
- `entities`: each needs `x` and `y` in world units. `id` keeps a marker stable
  from packet to packet, `kind` is `player`, `ally` or `other`, `heading` is in
  degrees clockwise with 0 pointing up, `label` is drawn next to the marker.
- Short form for a single player: `{"map": "castle", "x": 1, "y": 2, "heading": 0}`

Send at least one packet every 3 seconds, otherwise the tile hides itself.
10 per second gives smooth movement. A marker that is no longer sent disappears
after 9 seconds.

## Map definitions

Put the image and a `.toml` of the same name into `~/.config/sidehud/maps/`:

```toml
# ~/.config/sidehud/maps/castle.toml
name = "Castle"
image = "castle.png"
origin_px = [512, 512]        # pixel of world position (0, 0)
px_per_unit = [0.5, -0.5]     # pixels per world unit, x and y
```

A negative `px_per_unit` flips an axis. Most games count y upwards while image
rows count downwards, hence the minus. To calibrate, note two positions in the
game and where they sit on the image, then solve for scale and origin.

Without an image sidehud draws a grid around the markers, which is enough to
check that data arrives. `examples/maps/` has a demo map.

## Sending from Python

```python
import json, socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(json.dumps({"map": "castle", "x": x, "y": y, "heading": h}).encode(), ("127.0.0.1", 8766))
```

`examples/sender.py` moves three markers around and is a good starting point.

## Tapping the tile

Tap cycles through follow ×2, follow ×4 and the whole map.

## What this is not

sidehud does not read another process's memory and will not. Positions have to
come from something the game exposes on purpose: a modding API, a telemetry
interface, a log or save file. For online games this feature is not appropriate.
