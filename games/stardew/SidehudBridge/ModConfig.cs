namespace SidehudBridge;

public class ModConfig
{
    public string Host { get; set; } = "127.0.0.1";
    public int Port { get; set; } = 8766;
    public int SendsPerSecond { get; set; } = 10;
    public string MapsDir { get; set; } = "~/.config/sidehud/maps/stardew";
    public float MapScale { get; set; } = 0.25f;
    public int MapRefreshSeconds { get; set; } = 10;
    public bool SendNpcs { get; set; } = true;
    public bool SendMonsters { get; set; } = true;
    public bool SendIcons { get; set; } = true;
    public bool ExportMaps { get; set; } = true;
}
