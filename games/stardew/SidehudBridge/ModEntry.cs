using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using HarmonyLib;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using SkiaSharp;
using StardewModdingAPI;
using StardewModdingAPI.Events;
using StardewValley;
using StardewValley.Locations;
using StardewValley.Monsters;
using StardewValley.Network;

namespace SidehudBridge;

public class ModEntry : Mod
{
    const int Chunk = 2048;  // world pixels per draw, the size the game's own map screenshot uses

    ModConfig config = null!;
    UdpClient udp = null!;
    string mapsDir = "";
    uint interval;
    bool socketFailed;
    readonly HashSet<string> loggedErrors = new();

    GameLocation? tracked;
    string saveId = "";
    string mapId = "";
    string mapFile = "";
    string mapVersion = "";
    double[] mapOrigin = { 0, 0 };
    bool mapReady;

    RenderTarget2D? mapTarget, chunkTarget, chunkLightmap;
    Color[]? pixels;
    int chunk = -1, cols, rows, startX, startY, renderDelay;
    double nextRender;
    Task? saveTask;
    string saveDst = "";
    bool renderBroken;
    static bool hideCharacters;

    readonly Dictionary<string, string?> icons = new();
    readonly ConcurrentQueue<string> iconsDone = new();
    readonly long session = DateTime.UtcNow.Ticks;

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
        helper.Events.GameLoop.ReturnedToTitle += (_, _) => Reset();
        helper.Events.GameLoop.SaveLoaded += (_, _) => Guard("cleanup", RemoveLeftovers);
        helper.Events.Player.Warped += (_, e) => { if (e.IsLocalPlayer) Track(e.NewLocation); };
        Guard("harmony", () =>
        {
            var harmony = new Harmony(ModManifest.UniqueID);
            var postfix = new HarmonyMethod(typeof(ModEntry), nameof(HideWhileRendering));
            foreach (Type type in new[] { typeof(GameLocation), typeof(BusStop), typeof(Desert) })
                harmony.Patch(AccessTools.DeclaredMethod(type, nameof(GameLocation.shouldHideCharacters)), postfix: postfix);
        });
    }

    // the map is drawn from the running world; farmers and npcs are markers, not part of the picture
    static void HideWhileRendering(ref bool __result)
    {
        if (hideCharacters) __result = true;
    }

    void Reset()
    {
        tracked = null;
        chunk = -1;
        saveTask = null;
        pixels = null;
        mapTarget?.Dispose();
        chunkTarget?.Dispose();
        chunkLightmap?.Dispose();
        mapTarget = chunkTarget = chunkLightmap = null;
    }

    void OnUpdateTicked(object? sender, UpdateTickedEventArgs e)
    {
        if (!Context.IsWorldReady) return;
        while (iconsDone.TryDequeue(out string? key)) icons[key] = $"stardew/icons/{key}.png?v={session}";
        if (saveTask is { IsCompleted: true }) FinishSave();
        if (config.ExportMaps && !renderBroken)
        {
            try { RenderStep(); }
            catch (Exception ex)
            {
                renderBroken = true;
                chunk = -1;
                try { Game1.spriteBatch.End(); } catch (Exception) { }
                Monitor.Log($"live map stopped: {ex}", LogLevel.Warn);
            }
        }
        if (e.IsMultipleOf(interval)) Send();
    }

    void Track(GameLocation loc)
    {
        tracked = loc;
        saveId = Clean(StardewModdingAPI.Constants.SaveFolderName ?? "unsaved");
        mapId = Clean(loc.NameOrUniqueName);
        bool fixedLayout = loc is not (MineShaft or VolcanoDungeon) && !loc.IsTemporary;
        // mine levels share one file, a level looks different on every visit anyway
        mapFile = fixedLayout ? mapId : "_level";
        string path = MapPath();
        mapReady = fixedLayout && File.Exists(path);
        mapVersion = mapReady ? File.GetLastWriteTimeUtc(path).Ticks.ToString() : "";
        chunk = -1;
        renderDelay = 30;
        nextRender = 0;
        Region(loc, out startX, out startY, out _, out _);
        double px = Math.Round(64 * config.MapScale, 2);
        mapOrigin = new[] { -startX / 64.0 * px, -startY / 64.0 * px };
    }

    static string Clean(string s) => Regex.Replace(s, "[^A-Za-z0-9_-]", "_");

    string MapPath() => Path.Combine(mapsDir, saveId, mapFile + ".png");

    // the part of the map the game's own screenshot covers: all of it, or its ScreenshotRegion (tiles)
    static void Region(GameLocation loc, out int x, out int y, out int w, out int h)
    {
        x = 0;
        y = 0;
        w = loc.map.DisplayWidth;
        h = loc.map.DisplayHeight;
        string[] r = loc.GetMapPropertySplitBySpaces("ScreenshotRegion");
        if (r.Length >= 4 && int.TryParse(r[0], out int left) && int.TryParse(r[1], out int top) && int.TryParse(r[2], out int right) && int.TryParse(r[3], out int bottom))
        {
            x = left * 64;
            y = top * 64;
            w = (right + 1) * 64 - x;
            h = (bottom + 1) * 64 - y;
        }
    }

    void RenderStep()
    {
        var loc = Game1.currentLocation;
        if (loc == null || !ReferenceEquals(loc, tracked) || !Context.IsPlayerFree || Game1.game1.takingMapScreenshot)
        {
            chunk = -1;
            return;
        }
        if (chunk < 0)
        {
            if (renderDelay > 0)
            {
                renderDelay--;
                return;
            }
            if (saveTask != null || Game1.currentGameTime.TotalGameTime.TotalSeconds < nextRender) return;
            StartPass(loc);
        }
        DrawChunk();
    }

    void StartPass(GameLocation loc)
    {
        Region(loc, out startX, out startY, out int w, out int h);
        int pw = (int)(w * config.MapScale), ph = (int)(h * config.MapScale);
        var device = Game1.graphics.GraphicsDevice;
        if (mapTarget == null || mapTarget.Width != pw || mapTarget.Height != ph)
        {
            mapTarget?.Dispose();
            mapTarget = new RenderTarget2D(device, pw, ph, false, SurfaceFormat.Color, DepthFormat.None, 0, RenderTargetUsage.PreserveContents);
        }
        chunkTarget ??= new RenderTarget2D(device, Chunk, Chunk, false, SurfaceFormat.Color, DepthFormat.None, 0, RenderTargetUsage.DiscardContents);
        cols = (w + Chunk - 1) / Chunk;
        rows = (h + Chunk - 1) / Chunk;
        chunk = 0;
    }

    // one piece of the map per tick; the same steps Game1.takeMapScreenshot runs in one go
    void DrawChunk()
    {
        int col = chunk % cols, row = chunk / cols;
        float scale = config.MapScale;
        var device = Game1.graphics.GraphicsDevice;
        var lightmap = Helper.Reflection.GetField<RenderTarget2D>(typeof(Game1), "_lightmap");
        var gameLightmap = lightmap.GetValue();
        var viewport = Game1.viewport;
        bool hud = Game1.displayHUD, lit = Game1.drawLighting;
        float zoom = Game1.options.baseZoomLevel;
        bool begun = false;
        try
        {
            Game1.game1.takingMapScreenshot = true;
            Game1.options.baseZoomLevel = 1f;
            Game1.drawLighting = false;
            hideCharacters = true;
            lightmap.SetValue(chunkLightmap!);  // null on the first chunk, allocateLightmap then creates one
            Helper.Reflection.GetMethod(typeof(Game1), "allocateLightmap").Invoke(Chunk, Chunk);
            chunkLightmap = lightmap.GetValue();
            Game1.viewport = new xTile.Dimensions.Rectangle(col * Chunk + startX, row * Chunk + startY, Chunk, Chunk);
            Helper.Reflection.GetMethod(Game1.game1, "_draw").Invoke(Game1.currentGameTime, chunkTarget);
            device.SetRenderTarget(mapTarget);
            Game1.spriteBatch.Begin(SpriteSortMode.Deferred, BlendState.Opaque, SamplerState.PointClamp, DepthStencilState.Default, RasterizerState.CullNone);
            begun = true;
            Game1.spriteBatch.Draw(chunkTarget, new Vector2(col * Chunk * scale, row * Chunk * scale), null, Color.White, 0f, Vector2.Zero, scale, SpriteEffects.None, 1f);
        }
        finally
        {
            if (begun) Game1.spriteBatch.End();
            device.SetRenderTarget(null);
            lightmap.SetValue(gameLightmap);
            Game1.options.baseZoomLevel = zoom;
            Game1.game1.takingMapScreenshot = false;
            Game1.displayHUD = hud;
            Game1.drawLighting = lit;
            Game1.viewport = viewport;
            hideCharacters = false;
        }
        if (++chunk < cols * rows) return;
        chunk = -1;
        nextRender = config.MapRefreshSeconds > 0 ? Game1.currentGameTime.TotalGameTime.TotalSeconds + config.MapRefreshSeconds : double.MaxValue;
        SaveMap();
    }

    void SaveMap()
    {
        var target = mapTarget!;
        if (pixels == null || pixels.Length != target.Width * target.Height) pixels = new Color[target.Width * target.Height];
        target.GetData(pixels);
        Color[] px = pixels;
        int w = target.Width, h = target.Height;
        string dst = saveDst = MapPath();
        saveTask = Task.Run(() => WritePng(dst, px, w, h, SKAlphaType.Opaque));
    }

    void FinishSave()
    {
        if (saveTask!.IsFaulted)
        {
            if (loggedErrors.Add("save map")) Monitor.Log($"save map: {saveTask.Exception?.InnerException}", LogLevel.Trace);
        }
        else if (saveDst == MapPath())
        {
            mapReady = true;
            mapVersion = DateTime.UtcNow.Ticks.ToString();
        }
        saveTask = null;
    }

    // runs on a worker thread; the file is swapped in whole so sidehud never serves half a png
    static void WritePng(string path, Color[] px, int w, int h, SKAlphaType alpha)
    {
        byte[] bytes = MemoryMarshal.AsBytes(px.AsSpan()).ToArray();
        using var image = SKImage.FromPixelCopy(new SKImageInfo(w, h, SKColorType.Rgba8888, alpha), bytes) ?? throw new IOException("could not build image");
        using var data = image.Encode(SKEncodedImageFormat.Png, 100);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string tmp = path + ".tmp";
        using (var file = File.Create(tmp)) data.SaveTo(file);
        File.Move(tmp, path, true);
    }

    // one picture per kind of character, written on first sight; null until the file is on disk
    string? Icon(string key, Func<(Color[] px, int w, int h)> grab)
    {
        if (!config.SendIcons) return null;
        if (icons.TryGetValue(key, out string? rel)) return rel;
        icons[key] = null;
        var (px, w, h) = grab();
        string path = Path.Combine(mapsDir, "icons", key + ".png");
        Task.Run(() => WritePng(path, px, w, h, SKAlphaType.Premul))
            .ContinueWith(t => { if (t.IsCompletedSuccessfully) iconsDone.Enqueue(key); });
        return null;
    }

    static (Color[], int, int) Crop(Texture2D texture, Rectangle rect, Color tint)
    {
        rect = Rectangle.Intersect(rect, texture.Bounds);
        var px = new Color[rect.Width * rect.Height];
        texture.GetData(0, rect, px, 0, px.Length);
        if (tint != Color.White)
            for (int i = 0; i < px.Length; i++)
                px[i] = new Color(px[i].R * tint.R / 255, px[i].G * tint.G / 255, px[i].B * tint.B / 255, px[i].A);
        return (px, rect.Width, rect.Height);
    }

    // the head the game shows on its own map page
    static (Color[], int, int) Portrait(Farmer f)
    {
        var device = Game1.graphics.GraphicsDevice;
        using var target = new RenderTarget2D(device, 36, 36);
        device.SetRenderTarget(target);
        try
        {
            device.Clear(Color.Transparent);
            Game1.spriteBatch.Begin(SpriteSortMode.Deferred, BlendState.AlphaBlend, SamplerState.PointClamp);
            try { f.FarmerRenderer.drawMiniPortrat(Game1.spriteBatch, new Vector2(2, 2), 0f, 2f, 2, f); }
            finally { Game1.spriteBatch.End(); }
        }
        finally { device.SetRenderTarget(null); }
        var px = new Color[36 * 36];
        target.GetData(px);
        return (px, 36, 36);
    }

    static string TextureKey(AnimatedSprite sprite, string fallback) =>
        Clean(string.IsNullOrEmpty(sprite.Texture?.Name) ? fallback : sprite.Texture.Name);

    // exports copied by 0.2.0 while the game still held the file stayed in its Screenshots folder
    void RemoveLeftovers()
    {
        foreach (string f in Directory.GetFiles(Game1.game1.GetScreenshotFolder(false), "sidehud_*.png"))
            if (DateTime.UtcNow - File.GetLastWriteTimeUtc(f) > TimeSpan.FromMinutes(1))
                File.Delete(f);
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
            image = mapReady ? $"stardew/{saveId}/{mapFile}.png?v={mapVersion}" : null,
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
        Guard("player", () => list.Add(new { id = "player", kind = "player", x = Tile(me.StandingPixel.X), y = Tile(me.StandingPixel.Y), heading = me.FacingDirection * 90, label = me.Name, icon = Icon("farmer_" + me.UniqueMultiplayerID, () => Portrait(me)) }));
        Guard("farmers", () =>
        {
            foreach (Farmer f in loc.farmers)
                if (!f.IsLocalPlayer)
                    list.Add(new { id = "farmer:" + f.UniqueMultiplayerID, kind = "ally", x = Tile(f.StandingPixel.X), y = Tile(f.StandingPixel.Y), label = f.Name, icon = Icon("farmer_" + f.UniqueMultiplayerID, () => Portrait(f)) });
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
                    {
                        // slimes share one grey texture and get their colour at draw time
                        Color tint = m is GreenSlime slime ? slime.color.Value : Color.White;
                        string key = TextureKey(m.Sprite, m.Name) + (tint == Color.White ? "" : "_" + tint.PackedValue.ToString("x8"));
                        list.Add(new { id = "monster:" + monsters++, kind = "other", x = Tile(m.StandingPixel.X), y = Tile(m.StandingPixel.Y), label = Label(m),
                            icon = Icon(key, () => Crop(m.Sprite.Texture, new Rectangle(0, 0, m.Sprite.SpriteWidth, m.Sprite.SpriteHeight), tint)) });
                    }
                }
                else if (config.SendNpcs && npc.IsVillager && !npc.IsInvisible)
                    list.Add(new { id = "npc:" + npc.Name, kind = "ally", x = Tile(npc.StandingPixel.X), y = Tile(npc.StandingPixel.Y), label = Label(npc),
                        icon = Icon(TextureKey(npc.Sprite, npc.Name), () => Crop(npc.Sprite.Texture, npc.getMugShotSourceRect(), Color.White)) });
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
