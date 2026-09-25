# Working on sidehud

sidehud turns a phone into a second screen for a Linux gaming PC. A small
Python server on the PC collects sensor data and positions from games; a static
web page on the phone polls it and draws tiles: FPS, GPU, CPU, memory,
network, processes, a minimap and one panel per game.

Start with `README.md` for what the user sees and `docs/plugin-spec.md` for the
contract between games and sidehud.

## Layout

```
sidehud/
  cli.py          command line: serve (default), check, mangohud-setup
  config.py       defaults, merged with ~/.config/sidehud/config.toml
  server.py       HTTP: static page, /api/stats, /api/map, /api/games, /maps/<path>
  sampler.py      thread that reads every sensor once a second, keeps 2 minutes of history
  sensors/        nvidia-smi, amdgpu sysfs, psutil, MangoHud CSV log
  maps/           UDP listener, latest packet (state.py), .toml map definitions (defs.py)
  static/         the page: index.html, style.css, app.js, games/<id>.js panels
games/stardew/    SMAPI mod in C# that sends Stardew Valley data
examples/         sender.py (moving markers), stardew_fake.py (Stardew packets), maps/ demo map
contrib/          systemd user unit
docs/             plugin-spec.md, packet.schema.json
tests/            unittest
```

## How data moves

1. Sensors are read by `Sampler` once a second and served at `/api/stats`.
2. A game sender pushes JSON packets over UDP to `127.0.0.1:8766`. `MapState`
   keeps the newest one. `/api/map` returns it with the map resolved: a string
   id becomes the matching `.toml`, relative image paths get the `/maps/`
   prefix.
3. The page polls `/api/stats` every second and `/api/map` every 100 ms while a
   game sends, every second otherwise. It loads `static/games/<game>.js` for the
   game named in the packet. `/api/games` lists the modules for the profile menu.

## Commands

```
python -m sidehud serve                  # prints http://<lan ip>:8765
python -m sidehud check                  # what was detected on this PC
python -m unittest discover -s tests
python examples/stardew_fake.py          # Stardew packets without the game
python examples/sender.py --map demo     # needs examples/maps/demo.* in ~/.config/sidehud/maps
games/stardew/build.sh                   # needs dotnet-sdk, installs into the game's Mods folder
```

The server has to be restarted after Python changes. Static files are sent
with `Cache-Control: no-cache`, a page reload is enough for them.

## Conventions

- Python 3.11 or newer, standard library plus `psutil`. No other dependencies.
- The page is plain HTML, CSS and JavaScript: no build step, no npm, no
  framework. It has to work in Safari on iOS.
- Every UI string goes into `STRINGS` in `app.js`, in English and German.
  Panel modules keep their own strings in both languages.
- Colours only through the CSS variables in `style.css`. `--warn`, `--crit`
  and `--good` mean a state and are not used for anything else.
- Values from packets reach the DOM through `textContent`, never `innerHTML`.
- Tests use `unittest` from the standard library, one file per module. Every
  change to the server or the sensors comes with a test.
- Keep changes small and in the style of the surrounding code. Comments only
  where the code would otherwise be misread.
- Commit messages: one short line, lower case, no trailers.

## Rules for game integrations

Data comes only from interfaces a game offers for it: modding APIs, telemetry
SDKs, logs, save files. Nothing in this repository reads or writes another
process's memory, injects code, or touches games with anti-cheat or
competitive online play. `docs/plugin-spec.md` has the details.

## Things that are easy to get wrong

- Stardew Valley runs through Proton here, so the mod is a Windows .NET
  process under Wine. The mod maps `/` paths to `Z:` and finds the home folder
  through `WINEHOMEDIR` (`Expand` and `Home` in `ModEntry.cs`).
- `Game1.takeMapScreenshot` returns before the PNG is on disk and the game
  keeps the file locked for a while. The mod waits until the file ends with its
  `IEND` chunk before it copies it.
- SMAPI loads mods only at game start. After `build.sh` the game has to be
  restarted.
- MangoHud reads its config at game start. FPS need `autostart_log=1`,
  `output_folder` pointing where sidehud reads, and `log_duration=0`.
  `sidehud mangohud-setup` sets all three.
- UDP is bound to localhost. HTTP is bound to all interfaces and has no login,
  so anyone on the LAN can see the page.
- The page is plain http, so iOS offers no wake lock. The user has to turn off
  Auto-Lock.
- The profile choice lives in the phone's `localStorage`; `?profile=` in the
  URL overrides it.
