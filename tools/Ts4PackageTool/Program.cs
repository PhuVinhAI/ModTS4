using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Xml.Linq;
using LlamaLogic.Packages;
using LlamaLogic.Packages.Models;

return ProgramEntry.Run(args);

static class ProgramEntry
{
    static readonly JsonSerializerOptions jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static int Run(string[] args)
    {
        try
        {
            if (args.Length == 1 && args[0] == "version")
            {
                Console.WriteLine(GetLlamaLogicVersion());
                return 0;
            }

            if (args.Length == 3 && args[0] == "create")
            {
                CreatePackage(args[1], args[2]);
                return 0;
            }

            if (args.Length == 3 && args[0] == "encode-stbl")
            {
                EncodeStringTable(args[1], args[2]);
                return 0;
            }

            if (args.Length == 2 && args[0] == "validate")
            {
                ValidatePackage(args[1]);
                return 0;
            }

            Console.Error.WriteLine("Usage:");
            Console.Error.WriteLine("  Ts4PackageTool version");
            Console.Error.WriteLine("  Ts4PackageTool create <manifest.json> <output.package>");
            Console.Error.WriteLine("  Ts4PackageTool encode-stbl <strings.json> <output.stbl>");
            Console.Error.WriteLine("  Ts4PackageTool validate <input.package>");
            return 2;
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine(exception.Message);
            return 1;
        }
    }

    static void EncodeStringTable(string manifestPath, string outputPath)
    {
        manifestPath = Path.GetFullPath(manifestPath);
        outputPath = Path.GetFullPath(outputPath);
        var manifest = JsonSerializer.Deserialize<StringTableManifest>(
            File.ReadAllText(manifestPath), jsonOptions)
            ?? throw new InvalidDataException("String table manifest is empty.");
        if (manifest.Strings is null)
            throw new InvalidDataException("String table manifest has no strings object.");

        var strings = manifest.Strings
            .Select(entry => new KeyValuePair<uint, string>(
                ParseHexUInt32(entry.Key, "string table key"),
                entry.Value ?? throw new InvalidDataException(
                    $"String table value for {entry.Key} is null.")))
            .OrderBy(entry => entry.Key)
            .ToList();
        if (strings.Select(entry => entry.Key).Distinct().Count() != strings.Count)
            throw new InvalidDataException("String table manifest has duplicate keys.");

        var model = new StringTableModel();
        foreach (var entry in strings)
            model.Set(entry.Key, entry.Value);

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(outputDirectory))
            Directory.CreateDirectory(outputDirectory);
        File.WriteAllBytes(outputPath, model.Encode().ToArray());
    }

    static void ValidatePackage(string packagePath)
    {
        packagePath = Path.GetFullPath(packagePath);
        using var package = new DataBasePackedFile(packagePath);
        var interactionTuningCount = 0;
        var stringTableCount = 0;

        foreach (var key in package.Keys)
        {
            if (key.Type is ResourceType.StringTable)
            {
                package.GetModel<StringTableModel>(key);
                ++stringTableCount;
            }
            else if (key.Type is ResourceType.InteractionTuning)
            {
                var content = package.Get(key);
                var document = XDocument.Parse(Encoding.UTF8.GetString(content.Span));
                var root = document.Root
                    ?? throw new InvalidDataException($"Interaction tuning {key.FullTgi} has no root element.");
                var instanceText = root.Attribute("s")?.Value
                    ?? throw new InvalidDataException($"Interaction tuning {key.FullTgi} has no s attribute.");
                if (!ulong.TryParse(instanceText, NumberStyles.None, CultureInfo.InvariantCulture, out var instance)
                    || instance != key.FullInstance)
                    throw new InvalidDataException(
                        $"Interaction tuning {key.FullTgi} has mismatched XML instance {instanceText}.");
                ++interactionTuningCount;
            }
            else
            {
                package.Get(key);
            }
        }

        Console.WriteLine(
            $"Valid package: {package.Count} resources, {interactionTuningCount} interaction tuning, " +
            $"{stringTableCount} string tables.");
    }

    static void CreatePackage(string manifestPath, string outputPath)
    {
        manifestPath = Path.GetFullPath(manifestPath);
        outputPath = Path.GetFullPath(outputPath);
        var manifestJson = File.ReadAllText(manifestPath);
        var manifest = JsonSerializer.Deserialize<PackageManifest>(manifestJson, jsonOptions)
            ?? throw new InvalidDataException("Package manifest is empty.");
        if (manifest.Resources is null)
            throw new InvalidDataException("Package manifest has no resources array.");
        var manifestDirectory = Path.GetDirectoryName(manifestPath)
            ?? throw new InvalidDataException("Package manifest has no parent directory.");

        var resources = manifest.Resources
            .Select(resource => ParseResource(resource, manifestDirectory))
            .OrderBy(resource => (uint)resource.Key.Type)
            .ThenBy(resource => resource.Key.Group)
            .ThenBy(resource => resource.Key.FullInstance)
            .ToList();

        var duplicate = resources
            .GroupBy(resource => resource.Key)
            .FirstOrDefault(group => group.Count() > 1);
        if (duplicate is not null)
            throw new InvalidDataException($"Duplicate resource key: {duplicate.Key.FullTgi}");

        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrEmpty(outputDirectory))
            Directory.CreateDirectory(outputDirectory);

        using var package = new DataBasePackedFile
        {
            CreationTime = DateTimeOffset.UnixEpoch,
            UpdatedTime = DateTimeOffset.UnixEpoch
        };
        foreach (var resource in resources)
            package.Set(resource.Key, File.ReadAllBytes(resource.Path), resource.CompressionMode);
        package.SaveAs(outputPath, ResourceKeyOrder.TypeGroupInstance);
    }

    static ParsedResource ParseResource(ResourceManifest resource, string manifestDirectory)
    {
        ArgumentNullException.ThrowIfNull(resource);
        var type = ParseHexUInt32(resource.Type, "type");
        var group = ParseHexUInt32(resource.Group, "group");
        var instance = ParseHexUInt64(resource.Instance, "instance");
        if (string.IsNullOrWhiteSpace(resource.Path))
            throw new InvalidDataException("Resource path cannot be empty.");
        var resourcePath = Path.GetFullPath(resource.Path, manifestDirectory);
        if (!File.Exists(resourcePath))
            throw new FileNotFoundException("Resource payload does not exist.", resourcePath);

        return new ParsedResource(
            new ResourceKey((ResourceType)type, group, instance),
            resourcePath,
            ParseCompressionMode(resource.Compression));
    }

    static CompressionMode ParseCompressionMode(string? value) =>
        value?.ToLowerInvariant() switch
        {
            null or "auto" => CompressionMode.Auto,
            "off" => CompressionMode.ForceOff,
            "zlib" => CompressionMode.ForceZLib,
            "internal" => CompressionMode.ForceInternal,
            _ => throw new InvalidDataException($"Unknown compression mode: {value}")
        };

    static uint ParseHexUInt32(string? value, string field)
    {
        value = NormalizeHex(value, field);
        if (!uint.TryParse(value, NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture, out var result))
            throw new InvalidDataException($"Invalid hexadecimal {field}: {value}");
        return result;
    }

    static ulong ParseHexUInt64(string? value, string field)
    {
        value = NormalizeHex(value, field);
        if (!ulong.TryParse(value, NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture, out var result))
            throw new InvalidDataException($"Invalid hexadecimal {field}: {value}");
        return result;
    }

    static string NormalizeHex(string? value, string field)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new InvalidDataException($"Resource {field} cannot be empty.");
        return value.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? value[2..] : value;
    }

    static string GetLlamaLogicVersion()
    {
        var version = typeof(DataBasePackedFile).Assembly.GetName().Version
            ?? throw new InvalidOperationException("Cannot determine LlamaLogic.Packages version.");
        return $"{version.Major}.{version.Minor}.{version.Build}";
    }
}

sealed class PackageManifest
{
    public List<ResourceManifest>? Resources { get; init; } = [];
}

sealed class StringTableManifest
{
    public Dictionary<string, string?>? Strings { get; init; }
}

sealed class ResourceManifest
{
    public string? Type { get; init; }
    public string? Group { get; init; }
    public string? Instance { get; init; }
    public string? Path { get; init; }
    public string? Compression { get; init; }
}

sealed record ParsedResource(ResourceKey Key, string Path, CompressionMode CompressionMode);
