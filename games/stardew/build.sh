#!/usr/bin/env bash
# usage: ./build.sh ["/path/to/Stardew Valley"]
set -euo pipefail
cd "$(dirname "$0")/SidehudBridge"

game=${1:-}
if [ -z "$game" ]; then
    for vdf in ~/.local/share/Steam/steamapps/libraryfolders.vdf ~/.steam/steam/steamapps/libraryfolders.vdf; do
        [ -f "$vdf" ] || continue
        while read -r lib; do
            if [ -f "$lib/steamapps/common/Stardew Valley/StardewModdingAPI.dll" ]; then
                game="$lib/steamapps/common/Stardew Valley"
                break 2
            fi
        done < <(sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)".*/\1/p' "$vdf")
    done
fi
if [ ! -f "$game/StardewModdingAPI.dll" ]; then
    echo "Stardew Valley with SMAPI not found in the Steam libraries, pass the game folder as argument" >&2
    exit 1
fi
if ! command -v dotnet >/dev/null; then
    echo "dotnet not found. Arch: sudo pacman -S dotnet-sdk" >&2
    exit 1
fi

export GamePath=$game
dotnet build -c Release
echo "deployed to $game/Mods/SidehudBridge"
