using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Text.Json;
using System.Text.RegularExpressions;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Locations;
using StardewValley.Monsters;
using StardewValley.Network;

namespace SidehudBridge;

public class ModEntry : Mod
{
    ModConfig config = null!;
    UdpClient udp = null!;
    string mapsDir = "";
    uint interval;
    bool socketFailed;

    GameLocation? tracked;
    string mapId = "";
    double[] mapOrigin = { 0, 0 };
    bool mapReady;
    bool exportPending;
    int exportDelay;
    readonly HashSet<string> failedExports = new();
    string? pendingSrc;
    string pendingId = "";
    int pendingTicks;
    readonly HashSet<string> loggedErrors = new();

    public override void Entry(IModHelper helper)
    {
        config = helper.ReadConfig<ModConfig>();
        mapsDir = Expand(config.MapsDir);
        interval = (uint)Math.Max(1, 60 / Math.Max(1, config.SendsPerSecond));
        udp = new UdpClient();
        try { udp.Connect(config.Host, config.Port); }
        catch (Exception ex)
        {
            Monitor.Log($"udp {config.Host}:{config.Port}: {ex.Message}, using 127.0.0.1:8766", LogLevel.Warn);
            udp.Connect("127.0.0.1", 8766);
        }
        helper.Events.GameLoop.UpdateTicked += OnUpdateTicked;
        helper.Events.GameLoop.ReturnedToTitle += (_, _) => { tracked = null; exportPending = false; pendingSrc = null; };
        helper.Events.Player.Warped += OnWarped;
    }

    void OnWarped(object? sender, WarpedEventArgs e)
    {
        if (e.IsLocalPlayer) Track(e.NewLocation);
    }

    void OnUpdateTicked(object? sender, UpdateTickedEventArgs e)
    {
        if (!Context.IsWorldReady) return;
        if (exportPending && --exportDelay <= 0 && Context.CanPlayerMove && !Game1.eventUp && ReferenceEquals(Game1.currentLocation, tracked))
            ExportMap();
        if (pendingSrc != null) FinishExport();
        if (e.IsMultipleOf(interval)) Send();
    }

    void Track(GameLocation loc)
    {
        tracked = loc;
        mapId = Regex.Replace(loc.NameOrUniqueName, "[^A-Za-z0-9_-]", "_");
        bool fixedLayout = loc is not (MineShaft or VolcanoDungeon) && !loc.IsTemporary;
        mapReady = fixedLayout && File.Exists(MapPath(mapId));
        exportPending = config.ExportMaps && fixedLayout && !mapReady && !failedExports.Contains(mapId);
        exportDelay = 30;
        // takeMapScreenshot crops to the map's ScreenshotRegion (left top right bottom, tiles)
        int ox = 0, oy = 0;
        string[] r = loc.GetMapPropertySplitBySpaces("ScreenshotRegion");
        if (r.Length >= 4 && int.TryParse(r[0], out int l) && int.TryParse(r[1], out int t) && int.TryParse(r[2], out _) && int.TryParse(r[3], out _)) { ox = l; oy = t; }
        double px = Math.Round(64 * config.MapScale, 2);
        mapOrigin = new[] { -ox * px, -oy * px };
    }

    string MapPath(string id) => Path.Combine(mapsDir, id + ".png");

    void ExportMap()
    {
        exportPending = false;
        string id = mapId;
        try
        {
            // the screenshot is lit like the current frame; drawLighting is only touched in update code
            bool lit = Game1.drawLighting;
            Game1.drawLighting = false;
            string? file;
            try { file = Game1.game1.takeMapScreenshot(config.MapScale, "sidehud_" + id, null); }
            finally { Game1.drawLighting = lit; }
            if (file == null) throw new IOException("game returned no screenshot");
            pendingSrc = Path.Combine(Game1.game1.GetScreenshotFolder(true), file);
            pendingId = id;
            pendingTicks = 0;
        }
        catch (Exception ex)
        {
            failedExports.Add(id);
            Monitor.Log($"map export {id}: {ex.Message}", LogLevel.Trace);
        }
    }

    // the game keeps writing (and holding) the png for a while after takeMapScreenshot returns
    void FinishExport()
    {
        if (++pendingTicks % 10 != 0) return;
        string src = pendingSrc!, id = pendingId;
        try
        {
            if (!PngComplete(src))
            {
                if (pendingTicks > 900) Abandon(id, "png never completed");
                return;
            }
            Directory.CreateDirectory(mapsDir);
            File.Copy(src, MapPath(id), true);
            try { File.Delete(src); } catch (Exception) { }
            if (id == mapId) mapReady = true;
            pendingSrc = null;
            Monitor.Log($"map exported to {MapPath(id)}", LogLevel.Info);
        }
        catch (IOException ex)
        {
            if (pendingTicks > 900) Abandon(id, ex.Message);
        }
    }

    void Abandon(string id, string why)
    {
        pendingSrc = null;
        failedExports.Add(id);
        Monitor.Log($"map export {id}: {why}", LogLevel.Trace);
    }

    static bool PngComplete(string path)
    {
        using var f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        if (f.Length < 12) return false;
        f.Seek(-8, SeekOrigin.End);
        var tail = new byte[4];
        return f.Read(tail, 0, 4) == 4 && tail[0] == (byte)'I' && tail[1] == (byte)'E' && tail[2] == (byte)'N' && tail[3] == (byte)'D';
    }

    void Send()
    {
        var loc = Game1.currentLocation;
        if (loc == null) return;
        if (!ReferenceEquals(loc, tracked)) Track(loc);
        double px = Math.Round(64 * config.MapScale, 2);
        object? map = null;
        Guard("map", () => map = new
        {
            id = "stardew/" + mapId,
            name = loc.DisplayName,
            image = mapReady ? "stardew/" + mapId + ".png" : null,
            origin_px = mapOrigin,
            px_per_unit = new[] { px, px },
        });
        var msg = new { game = "stardew", source = "smapi", map, entities = Entities(loc), stats = Stats(loc) };
        byte[] data = JsonSerializer.SerializeToUtf8Bytes(msg);
        try
        {
            udp.Send(data, data.Length);
        }
        catch (SocketException ex)
        {
            if (!socketFailed) Monitor.Log($"udp {config.Host}:{config.Port}: {ex.Message}", LogLevel.Trace);
            socketFailed = true;
        }
    }

    List<object> Entities(GameLocation loc)
    {
        var list = new List<object>();
        var me = Game1.player;
        Guard("player", () => list.Add(new { id = "player", kind = "player", x = Tile(me.StandingPixel.X), y = Tile(me.StandingPixel.Y), heading = me.FacingDirection * 90, label = me.Name }));
        Guard("farmers", () =>
        {
            foreach (Farmer f in loc.farmers)
                if (!f.IsLocalPlayer)
                    list.Add(new { id = "farmer:" + f.UniqueMultiplayerID, kind = "ally", x = Tile(f.StandingPixel.X), y = Tile(f.StandingPixel.Y), label = f.Name });
        });
        Guard("npcs", () =>
        {
            int monsters = 0;
            foreach (NPC npc in loc.characters)
            {
                if (list.Count >= 80) break;
                if (npc is Monster m)
                {
                    if (config.SendMonsters)
                        list.Add(new { id = "monster:" + monsters++, kind = "other", x = Tile(m.StandingPixel.X), y = Tile(m.StandingPixel.Y), label = Label(m) });
                }
                else if (config.SendNpcs && npc.IsVillager && !npc.IsInvisible)
                    list.Add(new { id = "npc:" + npc.Name, kind = "ally", x = Tile(npc.StandingPixel.X), y = Tile(npc.StandingPixel.Y), label = Label(npc) });
            }
        });
        return list;
    }

    Dictionary<string, object?> Stats(GameLocation loc)
    {
        var s = new Dictionary<string, object?>();
        var p = Game1.player;
        Guard("date", () =>
        {
            s["day"] = Game1.dayOfMonth;
            s["season"] = Game1.currentSeason;
            s["year"] = Game1.year;
            s["weekday"] = Game1.Date.DayOfWeek.ToString()[..3];
            s["time"] = Game1.timeOfDay;
            s["timeText"] = Game1.getTimeOfDayString(Game1.timeOfDay);
        });
        Guard("weather", () => s["weather"] = Weather(loc.GetWeather()));
        Guard("stats", () =>
        {
            s["money"] = p.Money;
            s["energy"] = (int)p.Stamina;
            s["maxEnergy"] = p.MaxStamina;
            s["health"] = p.health;
            s["maxHealth"] = p.maxHealth;
            s["location"] = loc.DisplayName;
            s["luck"] = Math.Round(p.DailyLuck, 3);
            s["skills"] = new { farming = p.FarmingLevel, mining = p.MiningLevel, foraging = p.ForagingLevel, fishing = p.FishingLevel, combat = p.CombatLevel };
        });
        Guard("events", () =>
        {
            s["birthday"] = Utility.getTodaysBirthdayNPC()?.displayName;
            s["festival"] = Utility.isFestivalDay() && DataLoader.Festivals_FestivalDates(Game1.content).TryGetValue(Game1.currentSeason + Game1.dayOfMonth, out string? name) ? name : null;
        });
        return s;
    }

    // per-location weather; the Game1.isRaining flags only describe the valley
    static string Weather(LocationWeather w) =>
        w.IsLightning ? "storm" : w.IsGreenRain ? "greenrain" : w.IsRaining ? "rain" : w.IsSnowing ? "snow" : w.IsDebrisWeather ? "wind" : "sunny";

    static double Tile(int px) => Math.Round(px / 64.0, 2);

    static string Label(NPC n) => string.IsNullOrEmpty(n.displayName) ? n.Name : n.displayName;

    void Guard(string what, Action a)
    {
        try { a(); }
        catch (Exception ex) { if (loggedErrors.Add(what)) Monitor.Log($"{what}: {ex}", LogLevel.Trace); }
    }

    static string Expand(string path)
    {
        path = path.Replace("$XDG_CONFIG_HOME", Environment.GetEnvironmentVariable("XDG_CONFIG_HOME") ?? "~/.config");
        if (path.StartsWith("~")) path = Home() + path[1..];
        if (OperatingSystem.IsWindows() && path.StartsWith("/")) path = "Z:" + path;  // Proton: Wine maps / to Z:
        return path;
    }

    static string Home()
    {
        string? home = Environment.GetEnvironmentVariable("HOME");
        // Wine drops HOME from the Windows environment; WINEHOMEDIR is its NT path (\??\unix\home\<user> or \??\Z:\home\<user>)
        string? wine = Environment.GetEnvironmentVariable("WINEHOMEDIR");
        if (home == null && wine != null && wine.StartsWith(@"\??\"))
        {
            home = wine[4..].Replace('\\', '/');
            if (home.StartsWith("unix/")) home = home[4..];
        }
        return home ?? Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
    }
}
