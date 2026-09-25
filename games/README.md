# Games

A game gets its own panel next to the map when it announces itself in the UDP
packets. `sidehud/static/games/stardew.js` is the reference panel,
`examples/stardew_fake.py` feeds it without the game.

To add one:

1. Send the minimap packet (see [docs/minimap.md](../docs/minimap.md)) with two
   extra keys: `"game": "<id>"` and `"stats": {...}`. `stats` is whatever your
   panel wants to show, sidehud passes it through untouched. Keep sending while
   the game runs, 10 per second is plenty; stop and both tiles disappear.
2. Drop `sidehud/static/games/<id>.js`, an ES module:
   ```js
   export default {
     title: 'My Game',
     render(stats, root, ctx) { /* fill root, return { sub: 'right side of the label' } */ },
   };
   ```
   `render` runs on every packet, so build the DOM once and update text after
   that. All games share `root`, so check that your nodes are still attached
   (`isConnected`) and rebuild when another panel replaced them. `ctx` has `t`,
   `f0`, `f1`, `locale` and `lang` (`en` or `de`) from the page; the existing
   classes `.value`, `.kv`, `.meter`, `.caption` fit in.
3. Map images go to `~/.config/sidehud/maps/<id>/`. Either reference a `.toml`
   there by id or send `"map"` inline: `{"id": "<id>/Farm", "name": "Farm",
   "image": "<id>/Farm.png", "origin_px": [0, 0], "px_per_unit": [16, 16]}`.
   For a location without an image send the same object with `"image": null`:
   the grid then keeps the game's axes and shows the location name. `"map": null`
   draws the grid with y pointing up.
