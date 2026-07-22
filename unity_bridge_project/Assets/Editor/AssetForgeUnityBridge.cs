using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.U2D.Sprites;
using UnityEngine;

public static class AssetForgeUnityBridge
{
    [Serializable]
    private sealed class Command
    {
        public string operation;
        public string sourcePath;
        public string reportPath;
        public string presetPath;
        public string packagePath;
        public string workingAssetPath = "Assets/SpriteStationInput";
    }

    [Serializable]
    private sealed class SpriteSlice
    {
        public string name;
        public int[] rect;
    }

    [Serializable]
    private sealed class SpriteImportAsset
    {
        public string file;
        public string spriteMode;
        public string name;
        public string textureType;
        public bool alphaIsTransparency;
        public bool mipMaps;
        public string wrapMode;
        public string filterMode;
        public string compression;
        public float pixelsPerUnit;
        public float[] pivot;
        public List<SpriteSlice> slices = new List<SpriteSlice>();
    }

    [Serializable]
    private sealed class UnityImportPreset
    {
        public string schemaVersion;
        public string engine;
        public string assetName;
        public List<SpriteImportAsset> assets = new List<SpriteImportAsset>();
    }

    [Serializable]
    private sealed class SpritePreviewAsset
    {
        public string file;
        public string spriteMode;
        public int width;
        public int height;
        public int sliceCount;
        public bool valid;
        public string error;
    }

    [Serializable]
    private sealed class ClipReport
    {
        public string name;
        public float length;
        public float frameRate;
        public bool loopTime;
        public bool loopPose;
        public bool loopBlend;
    }

    [Serializable]
    private sealed class AssetReport
    {
        public string bridgeVersion = "0.1.0";
        public string unityVersion;
        public string operation;
        public string sourcePath;
        public string importedAssetPath;
        public string assetType;
        public bool hasAnimator;
        public bool isHuman;
        public bool isValidHuman;
        public int transformCount;
        public int skinnedMeshCount;
        public int meshRendererCount;
        public int materialCount;
        public int animationClipCount;
        public List<string> boneNames = new List<string>();
        public List<ClipReport> animationClips = new List<ClipReport>();
        public List<string> warnings = new List<string>();
        public bool readOnlyPreview;
        public string presetPath;
        public int spriteAssetCount;
        public int spriteSliceCount;
        public List<SpritePreviewAsset> spriteAssets = new List<SpritePreviewAsset>();
        public bool importSettingsApplied;
        public int appliedAssetCount;
        public string error;
    }

    public static void Execute()
    {
        var report = new AssetReport
        {
            unityVersion = Application.unityVersion
        };

        try
        {
            var commandPath = GetArgument("-assetForgeCommand");
            if (string.IsNullOrWhiteSpace(commandPath) || !File.Exists(commandPath))
                throw new FileNotFoundException("Sprite Station command JSON not found.", commandPath);

            var command = JsonUtility.FromJson<Command>(File.ReadAllText(commandPath));
            report.operation = command.operation;
            report.sourcePath = command.sourcePath;

            if (command.operation == "ping")
            {
                WriteReport(command.reportPath, report);
                return;
            }

            if (command.operation == "preview_sprite_import")
            {
                PreviewSpriteImport(command, report);
                WriteReport(command.reportPath, report);
                return;
            }

            if (command.operation == "apply_sprite_import")
            {
                ApplySpriteImport(command, report);
                WriteReport(command.reportPath, report);
                return;
            }

            if (command.operation != "analyze_asset")
                throw new InvalidOperationException("Unsupported operation: " + command.operation);

            AnalyzeAsset(command, report);
            WriteReport(command.reportPath, report);
        }
        catch (Exception ex)
        {
            report.error = ex.ToString();
            var commandPath = GetArgument("-assetForgeCommand");
            if (!string.IsNullOrWhiteSpace(commandPath) && File.Exists(commandPath))
            {
                try
                {
                    var command = JsonUtility.FromJson<Command>(File.ReadAllText(commandPath));
                    WriteReport(command.reportPath, report);
                }
                catch { }
            }
            Debug.LogException(ex);
            EditorApplication.Exit(2);
        }
    }

    private static void ApplySpriteImport(Command command, AssetReport report)
    {
        if (string.IsNullOrWhiteSpace(command.packagePath) || !Directory.Exists(command.packagePath))
            throw new DirectoryNotFoundException("Exported Unity package not found: " + command.packagePath);
        if (string.IsNullOrWhiteSpace(command.presetPath) || !File.Exists(command.presetPath))
            throw new FileNotFoundException("Unity sprite preset not found.", command.presetPath);

        var projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        var assetsRoot = Path.GetFullPath(Application.dataPath);
        var importsRoot = Path.GetFullPath(Path.Combine(assetsRoot, "SpriteStationImports"));
        var legacyImportsRoot = Path.GetFullPath(Path.Combine(assetsRoot, "AssetForgeImports"));
        var packageRoot = Path.GetFullPath(command.packagePath);
        var importsPrefix = importsRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        var legacyImportsPrefix = legacyImportsRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        var selectedImportsRoot = packageRoot.StartsWith(importsPrefix, StringComparison.OrdinalIgnoreCase)
            ? importsRoot
            : packageRoot.StartsWith(legacyImportsPrefix, StringComparison.OrdinalIgnoreCase)
                ? legacyImportsRoot
                : null;
        if (selectedImportsRoot == null)
            throw new InvalidDataException("Package must be inside Assets/SpriteStationImports (legacy AssetForgeImports is supported). ");
        if (!string.Equals(Path.GetDirectoryName(packageRoot), selectedImportsRoot, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Nested package paths are not supported.");
        var packagePrefix = packageRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;

        var presetPath = Path.GetFullPath(command.presetPath);
        if (!string.Equals(Path.GetDirectoryName(presetPath), packageRoot, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Preset must be stored in the exported package root.");
        var preset = JsonUtility.FromJson<UnityImportPreset>(File.ReadAllText(presetPath));
        if (preset == null || !string.Equals(preset.engine, "Unity", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Preset is not a Sprite Station Unity import preset.");
        if (preset.assets == null || preset.assets.Count == 0)
            throw new InvalidDataException("Preset contains no sprite assets.");

        report.presetPath = presetPath;
        report.spriteAssetCount = preset.assets.Count;
        foreach (var asset in preset.assets)
        {
            if (!string.Equals(asset.textureType, "Sprite", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Only Sprite textureType is supported.");
            if (!string.Equals(asset.spriteMode, "Single", StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(asset.spriteMode, "Multiple", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Unsupported spriteMode: " + asset.spriteMode);
            if (!string.Equals(asset.wrapMode, "Clamp", StringComparison.OrdinalIgnoreCase) ||
                !string.Equals(asset.filterMode, "Bilinear", StringComparison.OrdinalIgnoreCase) ||
                !string.Equals(asset.compression, "Uncompressed", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Preset contains unsupported texture settings.");

            var absolute = Path.GetFullPath(Path.Combine(packageRoot, asset.file.Replace('/', Path.DirectorySeparatorChar)));
            if (!absolute.StartsWith(packagePrefix, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Sprite path escapes the exported package.");
            if (!File.Exists(absolute))
                throw new FileNotFoundException("Sprite PNG not found.", absolute);

            var assetPath = "Assets/" + Path.GetRelativePath(assetsRoot, absolute).Replace('\\', '/');
            AssetDatabase.ImportAsset(assetPath, ImportAssetOptions.ForceSynchronousImport);
            var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
            if (importer == null)
                throw new InvalidDataException("Asset is not handled by TextureImporter: " + assetPath);

            importer.textureType = TextureImporterType.Sprite;
            importer.alphaIsTransparency = asset.alphaIsTransparency;
            importer.mipmapEnabled = asset.mipMaps;
            importer.wrapMode = TextureWrapMode.Clamp;
            importer.filterMode = FilterMode.Bilinear;
            importer.textureCompression = TextureImporterCompression.Uncompressed;
            importer.spritePixelsPerUnit = asset.pixelsPerUnit > 0 ? asset.pixelsPerUnit : 100f;

            if (string.Equals(asset.spriteMode, "Multiple", StringComparison.OrdinalIgnoreCase))
            {
                if (asset.slices == null || asset.slices.Count == 0)
                    throw new InvalidDataException("Multiple Sprite asset contains no slices.");
                report.spriteSliceCount += asset.slices.Count;
                importer.spriteImportMode = SpriteImportMode.Multiple;
                importer.SaveAndReimport();
                var factory = new SpriteDataProviderFactories();
                factory.Init();
                var dataProvider = factory.GetSpriteEditorDataProviderFromObject(importer);
                dataProvider.InitSpriteEditorDataProvider();
                var spriteRects = (asset.slices ?? new List<SpriteSlice>()).Select(slice =>
                {
                    if (slice.rect == null || slice.rect.Length != 4)
                        throw new InvalidDataException("Sprite slice rect must contain four integers.");
                    return new SpriteRect
                    {
                        name = slice.name,
                        rect = new Rect(slice.rect[0], slice.rect[1], slice.rect[2], slice.rect[3]),
                        alignment = SpriteAlignment.Custom,
                        pivot = new Vector2(0.5f, 0f),
                        spriteID = GUID.Generate()
                    };
                }).ToArray();
                dataProvider.SetSpriteRects(spriteRects);
                dataProvider.Apply();
            }
            else
            {
                importer.spriteImportMode = SpriteImportMode.Single;
                var pivot = asset.pivot != null && asset.pivot.Length == 2
                    ? new Vector2(asset.pivot[0], asset.pivot[1])
                    : new Vector2(0.5f, 0f);
                var settings = new TextureImporterSettings();
                importer.ReadTextureSettings(settings);
                settings.spriteAlignment = (int)SpriteAlignment.Custom;
                settings.spritePivot = pivot;
                importer.SetTextureSettings(settings);
            }

            importer.SaveAndReimport();
            report.appliedAssetCount++;
        }

        AssetDatabase.SaveAssets();
        report.importSettingsApplied = report.appliedAssetCount == report.spriteAssetCount;
    }

    private static void PreviewSpriteImport(Command command, AssetReport report)
    {
        if (string.IsNullOrWhiteSpace(command.presetPath) || !File.Exists(command.presetPath))
            throw new FileNotFoundException("Unity sprite preset not found.", command.presetPath);

        var presetPath = Path.GetFullPath(command.presetPath);
        var packageRoot = Path.GetDirectoryName(presetPath);
        var rootPrefix = packageRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        var preset = JsonUtility.FromJson<UnityImportPreset>(File.ReadAllText(presetPath));
        if (preset == null || !string.Equals(preset.engine, "Unity", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Preset is not a Sprite Station Unity import preset.");

        report.readOnlyPreview = true;
        report.presetPath = presetPath;
        report.spriteAssetCount = preset.assets != null ? preset.assets.Count : 0;

        foreach (var asset in preset.assets ?? new List<SpriteImportAsset>())
        {
            var item = new SpritePreviewAsset
            {
                file = asset.file,
                spriteMode = asset.spriteMode,
                sliceCount = asset.slices != null ? asset.slices.Count : 0,
                valid = false
            };
            report.spriteAssets.Add(item);
            report.spriteSliceCount += item.sliceCount;

            try
            {
                var absolute = Path.GetFullPath(Path.Combine(packageRoot, asset.file.Replace('/', Path.DirectorySeparatorChar)));
                if (!absolute.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Sprite path escapes the package directory.");
                if (!File.Exists(absolute))
                    throw new FileNotFoundException("Sprite PNG not found.", absolute);

                var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                try
                {
                    if (!ImageConversion.LoadImage(texture, File.ReadAllBytes(absolute), false))
                        throw new InvalidDataException("File is not a readable image.");
                    item.width = texture.width;
                    item.height = texture.height;

                    foreach (var slice in asset.slices ?? new List<SpriteSlice>())
                    {
                        if (slice.rect == null || slice.rect.Length != 4)
                            throw new InvalidDataException("Sprite slice rect must contain four integers.");
                        var x = slice.rect[0];
                        var y = slice.rect[1];
                        var width = slice.rect[2];
                        var height = slice.rect[3];
                        if (x < 0 || y < 0 || width <= 0 || height <= 0 ||
                            x + width > texture.width || y + height > texture.height)
                            throw new InvalidDataException("Sprite slice is outside image bounds: " + slice.name);
                    }
                    item.valid = true;
                }
                finally
                {
                    UnityEngine.Object.DestroyImmediate(texture);
                }
            }
            catch (Exception ex)
            {
                item.error = ex.Message;
                report.warnings.Add(asset.file + ": " + ex.Message);
            }
        }
    }

    private static void AnalyzeAsset(Command command, AssetReport report)
    {
        if (string.IsNullOrWhiteSpace(command.sourcePath) || !File.Exists(command.sourcePath))
            throw new FileNotFoundException("Source asset not found.", command.sourcePath);

        var folder = string.IsNullOrWhiteSpace(command.workingAssetPath)
            ? "Assets/SpriteStationInput"
            : command.workingAssetPath.Replace("\\", "/");

        if (!AssetDatabase.IsValidFolder(folder))
        {
            Directory.CreateDirectory(folder);
            AssetDatabase.Refresh();
        }

        var destination = folder.TrimEnd('/') + "/" + Path.GetFileName(command.sourcePath);
        File.Copy(command.sourcePath, Path.GetFullPath(destination), true);
        AssetDatabase.ImportAsset(destination, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);

        report.importedAssetPath = destination;
        var main = AssetDatabase.LoadMainAssetAtPath(destination);
        report.assetType = main != null ? main.GetType().FullName : "unknown";

        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(destination);
        if (prefab != null)
        {
            var transforms = prefab.GetComponentsInChildren<Transform>(true);
            report.transformCount = transforms.Length;
            report.boneNames = transforms.Select(t => t.name).Distinct().OrderBy(n => n).ToList();
            report.skinnedMeshCount = prefab.GetComponentsInChildren<SkinnedMeshRenderer>(true).Length;
            report.meshRendererCount = prefab.GetComponentsInChildren<MeshRenderer>(true).Length;
            report.materialCount = prefab.GetComponentsInChildren<Renderer>(true)
                .SelectMany(r => r.sharedMaterials)
                .Where(m => m != null)
                .Distinct()
                .Count();

            var animator = prefab.GetComponentInChildren<Animator>(true);
            report.hasAnimator = animator != null;
            if (animator != null && animator.avatar != null)
            {
                report.isHuman = animator.avatar.isHuman;
                report.isValidHuman = animator.avatar.isValid;
            }
        }

        var clips = AssetDatabase.LoadAllAssetsAtPath(destination).OfType<AnimationClip>()
            .Where(c => !c.name.StartsWith("__preview__"))
            .ToArray();

        report.animationClipCount = clips.Length;
        foreach (var clip in clips)
        {
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            report.animationClips.Add(new ClipReport
            {
                name = clip.name,
                length = clip.length,
                frameRate = clip.frameRate,
                loopTime = settings.loopTime,
                loopPose = settings.loopBlendOrientation || settings.loopBlendPositionY || settings.loopBlendPositionXZ,
                loopBlend = settings.loopBlend
            });
        }

        var importer = AssetImporter.GetAtPath(destination) as ModelImporter;
        if (importer != null)
        {
            if (importer.animationType == ModelImporterAnimationType.Human)
                report.warnings.Add("ModelImporter animation type is Humanoid.");
            if (importer.avatarSetup == ModelImporterAvatarSetup.NoAvatar)
                report.warnings.Add("No avatar is configured for this model.");
        }
    }

    private static void WriteReport(string path, AssetReport report)
    {
        if (string.IsNullOrWhiteSpace(path))
            throw new InvalidOperationException("reportPath is required.");

        var absolute = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(absolute));
        File.WriteAllText(absolute, JsonUtility.ToJson(report, true));
        Debug.Log("Sprite Station Unity report written: " + absolute);
    }

    private static string GetArgument(string name)
    {
        var args = Environment.GetCommandLineArgs();
        for (var i = 0; i < args.Length - 1; i++)
            if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                return args[i + 1];
        return null;
    }
}
