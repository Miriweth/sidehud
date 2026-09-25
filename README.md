# sidehud

Your phone as a second screen next to the monitor. The PC serves a small web
page, the phone shows it fullscreen: FPS and frametime from MangoHud, GPU and
CPU load, temperatures, clocks, VRAM, RAM, network, the busiest processes.
Optionally a minimap fed by the game or a mod. Nothing to install on the phone,
it runs in Safari or Chrome.

Built for a Linux gaming box with an iPhone lying in landscape beside the
keyboard. Any phone or tablet with a browser works.

## Requirements

- Linux, Python 3.11 or newer, `psutil` (Arch: `python-psutil`)
- NVIDIA: `nvidia-smi`, comes with the driver. AMD: nothing extra, sysfs is read directly.
- FPS: MangoHud

## Install

```
git clone https://github.com/miriweth/sidehud
cd sidehud
python -m sidehud
```

or

```
pipx install git+https://github.com/miriweth/sidehud
sidehud
```

The server prints its address, something like `http://192.168.178.30:8765`.
Open that on the phone. `sidehud check` shows what was detected on the PC.

## Phone

Safari: Share, then "Add to Home Screen". From then on it starts fullscreen
with its own icon. Set Auto-Lock to Never while it runs; a page served over
plain http cannot keep the screen awake by itself.

The page follows the phone's language (German or English), `?lang=en` forces
one. Portrait stacks the tiles, landscape fits everything on one screen without
scrolling. Touch a graph to read a value from the last two minutes.

## FPS

MangoHud can write a CSV log while a game runs, sidehud tails the newest one.

```
sidehud mangohud-setup
```

adds three lines to `~/.config/MangoHud/MangoHud.conf` and keeps a backup:

```
output_folder=~/.local/share/sidehud/mangohud
autostart_log=1
log_interval=500
```

From the next game start the big number at the top switches from GPU load to
FPS, with the frametime and the game's name underneath. The logs are small but
they add up, empty the folder now and then.

## Firewall

sidehud listens on all interfaces. With ufw:

```
sudo ufw allow from 192.168.178.0/24 to any port 8765 proto tcp
```

Use your own LAN range. There is no login: anyone on the network can see the
page, process names included. Bind to `127.0.0.1` if it should stay on the PC.

## Minimap

Anything that can send a UDP packet can put positions on the phone. The packet
format and how to calibrate a map image are in [docs/minimap.md](docs/minimap.md).
To see it without a game:

```
python examples/sender.py
```

The map tile appears when data arrives and disappears when it stops.

sidehud only draws what a game or mod hands over. It does not read game memory,
and nothing here is meant for online games.

## Configuration

Optional, `~/.config/sidehud/config.toml`:

```toml
port = 8765
bind = "0.0.0.0"
map_port = 8766
mangohud_dir = "~/.local/share/sidehud/mangohud"
maps_dir = "~/.config/sidehud/maps"

[thresholds]   # [warn, critical]
gpu_temp = [83, 90]
cpu_temp = [85, 93]
vram = [90, 97]
ram = [90, 97]
```

Command line flags override the file, see `sidehud serve --help`.

## Autostart

`contrib/sidehud.service` is a systemd user unit. Check the path inside, then:

```
cp contrib/sidehud.service ~/.config/systemd/user/
systemctl --user enable --now sidehud
```

## Development

```
python -m unittest discover -s tests
```

## Similar projects

- [Sidepanel](https://github.com/FrittenFritz/Sidepanel): the same idea for Windows, on top of LibreHardwareMonitor
- [Glances](https://github.com/nicolargo/glances), [Netdata](https://github.com/netdata/netdata): full system monitors with a web UI, not aimed at gaming
- [MangoHud](https://github.com/flightlessmango/MangoHud): the overlay whose log this reads

## License

MIT
