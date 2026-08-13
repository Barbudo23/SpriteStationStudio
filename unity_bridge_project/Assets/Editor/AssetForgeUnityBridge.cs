using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.U2D.Sprites;
using UnityEngine;

public static class AssetForgeUnityBridge
{
    private const string RequiredUnityVersion = "6000.4.0f1";
    private const string AnimationJobRoot = "Assets/SpriteStationAnimationJob";
    private const string AnimationSheetsRoot = AnimationJobRoot + "/Sheets";
    private const string AnimationClipsRoot = AnimationJobRoot + "/Clips";

    [Serializable]
    private sealed class Command
    {
        public string operation;
        public string sourcePath;
        public string reportPath;
        public string presetPath;
        public string packagePath;
        public string packageManifestPath;
        public string workingAssetPath;
    }

    [Serializable]
    private sealed class SpriteSlice
    {
        public string name;
        public int[] rect;
        public float[] pivot;
        public int sourceFrame;
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
        public string sourceManifestVersion;
        public string assetName;
        public string applicationMode;
        public AnimationTiming animationTiming;
        public List<SpriteImportAsset> assets = new List<SpriteImportAsset>();
    }

    [Serializable]
    private sealed class ApprovedPackageArtifact
    {
        public string path;
        public string sha256;
    }

    [Serializable]
    private sealed class ApprovedPackageManifest
    {
        public string schemaVersion;
        public string application;
        public string kind;
        public string reviewSha256;
        public int directionCount;
        public int frameCountPerDirection;
        public int artifactCount;
        public List<ApprovedPackageArtifact> artifacts = new List<ApprovedPackageArtifact>();
    }

    [Serializable]
    private sealed class AnimationReview
    {
        public string schemaVersion;
        public string application;
        public string kind;
        public string animationManifest;
        public string animationManifestSha256;
        public string sourceSha256;
        public string decision;
    }

    [Serializable]
    private sealed class AnimationFrameRange
    {
        public int start;
        public int end;
    }

    [Serializable]
    private sealed class AnimationTiming
    {
        public double fps;
        public string fpsSource;
        public int sourceFrameStep;
        public List<double> sampleTimesSeconds = new List<double>();
        public double durationSeconds;
        public string loopPolicy;
    }

    [Serializable]
    private sealed class AnimationCanvas
    {
        public int width;
        public int height;
        public bool transparent;
        public string colorMode;
    }

    [Serializable]
    private sealed class AnimationPivot
    {
        public string mode;
        public float[] normalized;
    }

    [Serializable]
    private sealed class AnimationNormalization
    {
        public AnimationPivot pivot;
    }

    [Serializable]
    private sealed class AnimationFrame
    {
        public int order;
        public int sourceFrame;
        public string file;
        public string sha256;
    }

    [Serializable]
    private sealed class AnimationDirection
    {
        public string id;
        public string sheet;
        public string sheetSha256;
        public List<AnimationFrame> frames = new List<AnimationFrame>();
    }

    [Serializable]
    private sealed class AnimationManifest
    {
        public string schemaVersion;
        public string application;
        public string module;
        public string assetName;
        public string actionName;
        public int directionCount;
        public AnimationFrameRange frameRange;
        public List<int> sampledFrames = new List<int>();
        public int frameCountPerDirection;
        public AnimationTiming timing;
        public AnimationCanvas canvas;
        public AnimationNormalization normalization;
        public List<AnimationDirection> directions = new List<AnimationDirection>();
        public string contactSheet;
        public string contactSheetSha256;
    }

    [Serializable]
    private sealed class AnimationClipBindingDescriptor
    {
        public string relativePath;
        public string componentType;
        public string propertyName;
    }

    [Serializable]
    private sealed class AnimationClipKeyframeDescriptor
    {
        public double timeSeconds;
        public string spriteName;
        public int sourceFrame;
        public bool terminal;
    }

    [Serializable]
    private sealed class AnimationClipDescriptor
    {
        public string name;
        public string directionId;
        public string spriteSheet;
        public string spriteSheetSha256;
        public double frameRate;
        public double durationSeconds;
        public bool loopTime;
        public AnimationClipBindingDescriptor binding;
        public List<AnimationClipKeyframeDescriptor> keyframes = new List<AnimationClipKeyframeDescriptor>();
    }

    [Serializable]
    private sealed class UnityAnimationClipDescriptor
    {
        public string schemaVersion;
        public string application;
        public string kind;
        public string sourceAnimationManifest;
        public string sourceAnimationManifestSha256;
        public string sourceUnityPreset;
        public string sourceUnityPresetSha256;
        public string assetName;
        public string actionName;
        public int clipCount;
        public List<AnimationClipDescriptor> clips = new List<AnimationClipDescriptor>();
    }

    [Serializable]
    private sealed class AnimationBuildFileReport
    {
        public string path;
        public string sha256;
        public string role;
    }

    [Serializable]
    private sealed class AnimationBuildKeyframeReport
    {
        public double timeSeconds;
        public string spriteName;
        public int sourceFrame;
        public bool terminal;
        public string spriteGuid;
        public long spriteLocalId;
    }

    [Serializable]
    private sealed class AnimationBuildClipReport
    {
        public string name;
        public string assetPath;
        public double frameRate;
        public double durationSeconds;
        public bool loopTime;
        public AnimationClipBindingDescriptor binding;
        public List<AnimationBuildKeyframeReport> keyframes = new List<AnimationBuildKeyframeReport>();
    }

    [Serializable]
    private sealed class AnimationClipBuildReport
    {
        public string schemaVersion = "1.0";
        public string application = "Sprite Station Studio";
        public string kind = "unity_animation_clip_build_report";
        public string unityVersion;
        public string operation = "create_animation_clips";
        public string sourcePackageSha256;
        public string generatedAssetRoot = AnimationJobRoot;
        public bool portableReloadVerified;
        public int clipCount;
        public int spriteSheetCount;
        public int keyframeCount;
        public List<string> warnings = new List<string>();
        public List<AnimationBuildFileReport> files = new List<AnimationBuildFileReport>();
        public List<AnimationBuildClipReport> clips = new List<AnimationBuildClipReport>();
    }

    private sealed class ValidatedAnimationPackage
    {
        public string Root;
        public string PackageManifestPath;
        public string PackageManifestSha256;
        public ApprovedPackageManifest Package;
        public AnimationManifest Manifest;
        public UnityImportPreset Preset;
        public UnityAnimationClipDescriptor Descriptor;
        public Dictionary<string, string> ArtifactPaths;
        public Dictionary<string, string> ArtifactHashes;
    }

    private sealed class SpriteIdentity
    {
        public string Guid;
        public long LocalId;
    }

    private sealed class AnimationJobVerification
    {
        public List<AnimationBuildClipReport> Clips;
        public Dictionary<string, SpriteIdentity> SpriteIdentities;
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

            var commandJson = File.ReadAllText(commandPath);
            var command = JsonUtility.FromJson<Command>(commandJson);
            if (command == null)
                throw new InvalidDataException("Sprite Station command JSON is invalid.");
            report.operation = command.operation;
            report.sourcePath = command.sourcePath;

            if (command.operation == "create_animation_clips")
            {
                ValidateAnimationClipCommand(commandJson, command);
                CreateAnimationClips(command);
                return;
            }

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
                    if (command != null &&
                        (!string.Equals(command.operation, "create_animation_clips", StringComparison.Ordinal) ||
                         string.IsNullOrWhiteSpace(command.reportPath) ||
                         !File.Exists(Path.GetFullPath(command.reportPath))))
                        WriteReport(command.reportPath, report);
                }
                catch { }
            }
            Debug.LogException(ex);
            EditorApplication.Exit(2);
        }
    }

    private static void ValidateAnimationClipCommand(string json, Command command)
    {
        var keys = ReadTopLevelJsonKeys(json);
        var allowed = new HashSet<string>(StringComparer.Ordinal)
        {
            "operation",
            "packageManifestPath",
            "reportPath"
        };
        if (keys.Count != 3 || keys.Any(key => !allowed.Contains(key)) ||
            !allowed.All(key => keys.Contains(key)))
            throw new InvalidDataException(
                "create_animation_clips accepts only operation, packageManifestPath, and reportPath.");
        if (!string.Equals(command.operation, "create_animation_clips", StringComparison.Ordinal))
            throw new InvalidDataException("Animation clip operation is invalid.");
        if (string.IsNullOrWhiteSpace(command.packageManifestPath))
            throw new InvalidDataException("packageManifestPath is required.");
        if (string.IsNullOrWhiteSpace(command.reportPath))
            throw new InvalidDataException("reportPath is required.");
        if (!string.IsNullOrWhiteSpace(command.sourcePath) ||
            !string.IsNullOrWhiteSpace(command.presetPath) ||
            !string.IsNullOrWhiteSpace(command.packagePath) ||
            !string.IsNullOrWhiteSpace(command.workingAssetPath))
            throw new InvalidDataException(
                "Standalone source, preset, descriptor, package, or working paths are forbidden.");
    }

    private static HashSet<string> ReadTopLevelJsonKeys(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
            throw new InvalidDataException("Command JSON is empty.");
        var keys = new HashSet<string>(StringComparer.Ordinal);
        var index = 0;
        SkipJsonWhitespace(json, ref index);
        if (index >= json.Length || json[index++] != '{')
            throw new InvalidDataException("Command JSON must be an object.");
        SkipJsonWhitespace(json, ref index);
        if (index < json.Length && json[index] == '}')
            throw new InvalidDataException("Command JSON is empty.");
        while (index < json.Length)
        {
            SkipJsonWhitespace(json, ref index);
            var key = ReadJsonString(json, ref index);
            if (!keys.Add(key))
                throw new InvalidDataException("Command JSON contains a duplicate property: " + key);
            SkipJsonWhitespace(json, ref index);
            if (index >= json.Length || json[index++] != ':')
                throw new InvalidDataException("Command JSON property is malformed.");
            SkipJsonWhitespace(json, ref index);
            SkipJsonValue(json, ref index);
            SkipJsonWhitespace(json, ref index);
            if (index >= json.Length)
                throw new InvalidDataException("Command JSON is incomplete.");
            if (json[index] == '}')
            {
                index++;
                break;
            }
            if (json[index++] != ',')
                throw new InvalidDataException("Command JSON object is malformed.");
        }
        SkipJsonWhitespace(json, ref index);
        if (index != json.Length)
            throw new InvalidDataException("Command JSON contains trailing data.");
        return keys;
    }

    private static string ReadJsonString(string json, ref int index)
    {
        if (index >= json.Length || json[index++] != '"')
            throw new InvalidDataException("Command JSON property name must be a string.");
        var value = new StringBuilder();
        while (index < json.Length)
        {
            var character = json[index++];
            if (character == '"')
                return value.ToString();
            if (character == '\\')
            {
                if (index >= json.Length)
                    throw new InvalidDataException("Command JSON escape is incomplete.");
                var escaped = json[index++];
                switch (escaped)
                {
                    case '"': value.Append('"'); break;
                    case '\\': value.Append('\\'); break;
                    case '/': value.Append('/'); break;
                    case 'b': value.Append('\b'); break;
                    case 'f': value.Append('\f'); break;
                    case 'n': value.Append('\n'); break;
                    case 'r': value.Append('\r'); break;
                    case 't': value.Append('\t'); break;
                    case 'u':
                        if (index + 4 > json.Length)
                            throw new InvalidDataException("Command JSON unicode escape is incomplete.");
                        int code;
                        if (!int.TryParse(
                            json.Substring(index, 4),
                            System.Globalization.NumberStyles.HexNumber,
                            System.Globalization.CultureInfo.InvariantCulture,
                            out code))
                            throw new InvalidDataException("Command JSON unicode escape is invalid.");
                        value.Append((char)code);
                        index += 4;
                        break;
                    default:
                        throw new InvalidDataException("Command JSON escape is invalid.");
                }
            }
            else
            {
                if (character < 0x20)
                    throw new InvalidDataException("Command JSON string contains a control character.");
                value.Append(character);
            }
        }
        throw new InvalidDataException("Command JSON string is incomplete.");
    }

    private static void SkipJsonValue(string json, ref int index)
    {
        if (index >= json.Length)
            throw new InvalidDataException("Command JSON value is missing.");
        if (json[index] == '"')
        {
            ReadJsonString(json, ref index);
            return;
        }
        if (json[index] == '{' || json[index] == '[')
        {
            var opening = json[index++];
            var closing = opening == '{' ? '}' : ']';
            var depth = 1;
            while (index < json.Length && depth > 0)
            {
                if (json[index] == '"')
                {
                    ReadJsonString(json, ref index);
                    continue;
                }
                if (json[index] == opening) depth++;
                else if (json[index] == closing) depth--;
                index++;
            }
            if (depth != 0)
                throw new InvalidDataException("Command JSON nested value is incomplete.");
            return;
        }
        var start = index;
        while (index < json.Length && json[index] != ',' && json[index] != '}')
            index++;
        if (string.IsNullOrWhiteSpace(json.Substring(start, index - start)))
            throw new InvalidDataException("Command JSON value is missing.");
    }

    private static void SkipJsonWhitespace(string json, ref int index)
    {
        while (index < json.Length && char.IsWhiteSpace(json[index]))
            index++;
    }

    private static void CreateAnimationClips(Command command)
    {
        if (!string.Equals(Application.unityVersion, RequiredUnityVersion, StringComparison.Ordinal))
            throw new InvalidOperationException(
                "Unity version mismatch. Required " + RequiredUnityVersion +
                ", running " + Application.unityVersion + ".");

        var reportPath = Path.GetFullPath(command.reportPath);
        if (Directory.Exists(reportPath) || File.Exists(reportPath))
            throw new IOException("Animation clip report already exists: " + reportPath);
        if (!string.Equals(Path.GetExtension(reportPath), ".json", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Animation clip report must be a JSON file.");

        var projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        var jobAbsolute = Path.GetFullPath(Path.Combine(projectRoot, AnimationJobRoot));
        var jobPrefix = jobAbsolute.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        if (reportPath.StartsWith(jobPrefix, StringComparison.OrdinalIgnoreCase) ||
            string.Equals(reportPath, jobAbsolute, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Animation clip report must be outside the generated asset root.");
        if (Directory.Exists(jobAbsolute) || File.Exists(jobAbsolute) ||
            File.Exists(jobAbsolute + ".meta"))
            throw new IOException("Generated animation asset root already exists: " + AnimationJobRoot);

        var package = ValidateApprovedAnimationPackage(command.packageManifestPath);
        var packagePrefix = package.Root.TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var assetsPrefix = Path.GetFullPath(Application.dataPath).TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (reportPath.StartsWith(packagePrefix, StringComparison.OrdinalIgnoreCase) ||
            reportPath.StartsWith(assetsPrefix, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException(
                "Animation clip report must be outside both the approved package and Unity Assets.");
        var generated = false;
        string portabilityDirectory = null;
        try
        {
            generated = true;
            CreateAnimationJobAssets(package, projectRoot);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);

            var firstVerification = VerifyAnimationJob(package, projectRoot);
            portabilityDirectory = Path.Combine(
                Path.GetTempPath(),
                "SpriteStationAnimationJob-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(portabilityDirectory);
            var preservedHashes = PreservePortableAssetPairs(package, projectRoot, portabilityDirectory);

            if (!AssetDatabase.DeleteAsset(AnimationJobRoot))
                throw new IOException("Unity could not delete the generated animation job for portability verification.");
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            if (Directory.Exists(jobAbsolute) || File.Exists(jobAbsolute + ".meta"))
                throw new IOException("Generated animation job was not fully removed before portable reload.");

            RestorePortableAssetPairs(package, projectRoot, portabilityDirectory, preservedHashes);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            VerifyRestoredAssetPairHashes(projectRoot, preservedHashes);
            var secondVerification = VerifyAnimationJob(package, projectRoot);
            VerifyStableSpriteIdentities(firstVerification, secondVerification);
            VerifyPackageFilesUnchanged(package);

            var report = BuildAnimationClipReport(package, projectRoot, secondVerification);
            WriteAnimationClipBuildReport(reportPath, report);
        }
        catch
        {
            if (generated)
                DeleteAnimationJobBestEffort(jobAbsolute);
            throw;
        }
        finally
        {
            if (!string.IsNullOrEmpty(portabilityDirectory) &&
                Directory.Exists(portabilityDirectory))
                Directory.Delete(portabilityDirectory, true);
        }
    }

    private static ValidatedAnimationPackage ValidateApprovedAnimationPackage(
        string packageManifestPathValue)
    {
        var packageManifestPath = Path.GetFullPath(packageManifestPathValue);
        if (!File.Exists(packageManifestPath))
            throw new FileNotFoundException("Approved animation package manifest not found.", packageManifestPath);
        if (!string.Equals(
            Path.GetFileName(packageManifestPath),
            "approved_animation_package.json",
            StringComparison.Ordinal))
            throw new InvalidDataException(
                "packageManifestPath must name approved_animation_package.json exactly.");
        RejectReparsePoint(packageManifestPath, "Approved package manifest");
        var root = Path.GetDirectoryName(packageManifestPath);
        if (string.IsNullOrEmpty(root))
            throw new InvalidDataException("Approved animation package root is invalid.");
        root = Path.GetFullPath(root);

        var package = ReadJsonFile<ApprovedPackageManifest>(
            packageManifestPath, "Approved animation package manifest");
        if (package.schemaVersion != "1.0" ||
            package.application != "Sprite Station Studio" ||
            package.kind != "approved_animation_package")
            throw new InvalidDataException("Approved animation package contract is unsupported.");
        if (package.artifacts == null || package.artifacts.Count == 0 ||
            package.artifactCount != package.artifacts.Count)
            throw new InvalidDataException("Approved animation package artifact list is inconsistent.");
        if (!IsSha256(package.reviewSha256))
            throw new InvalidDataException("Approved animation package review hash is invalid.");

        var artifactPaths = new Dictionary<string, string>(StringComparer.Ordinal);
        var artifactHashes = new Dictionary<string, string>(StringComparer.Ordinal);
        var insensitiveArtifactPaths = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var artifact in package.artifacts)
        {
            if (artifact == null)
                throw new InvalidDataException("Approved animation package contains an invalid artifact.");
            var relative = ValidateSafeRelativePath(root, artifact.path, "Approved package artifact");
            if (string.Equals(relative, "approved_animation_package.json", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Approved package manifest cannot list itself as an artifact.");
            if (!insensitiveArtifactPaths.Add(relative))
                throw new InvalidDataException(
                    "Approved animation package contains duplicate artifact paths, including case-only duplicates.");
            if (!IsSha256(artifact.sha256))
                throw new InvalidDataException("Approved package artifact hash is invalid: " + relative);
            var absolute = Path.GetFullPath(Path.Combine(
                root, relative.Replace('/', Path.DirectorySeparatorChar)));
            if (!File.Exists(absolute))
                throw new FileNotFoundException("Approved package artifact is missing.", absolute);
            RejectReparsePoint(absolute, "Approved package artifact");
            var actualHash = ComputeSha256(absolute);
            if (!string.Equals(actualHash, artifact.sha256, StringComparison.Ordinal))
                throw new InvalidDataException("Approved package artifact hash mismatch: " + relative);
            artifactPaths.Add(relative, absolute);
            artifactHashes.Add(relative, artifact.sha256);
        }

        var actualPaths = new HashSet<string>(StringComparer.Ordinal);
        var actualPathsInsensitive = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var file in Directory.GetFiles(root, "*", SearchOption.AllDirectories))
        {
            var absolute = Path.GetFullPath(file);
            RejectReparsePoint(absolute, "Approved package file");
            var relative = Path.GetRelativePath(root, absolute).Replace('\\', '/');
            if (!actualPathsInsensitive.Add(relative))
                throw new InvalidDataException(
                    "Approved package contains case-insensitive duplicate files: " + relative);
            if (!string.Equals(absolute, packageManifestPath, StringComparison.OrdinalIgnoreCase))
                actualPaths.Add(relative);
        }
        if (!actualPaths.SetEquals(artifactPaths.Keys))
            throw new InvalidDataException(
                "Approved package contains unlisted files or lists files that are not present.");

        string manifestPath;
        string presetPath;
        string descriptorPath;
        string reviewPath;
        if (!artifactPaths.TryGetValue("animation_manifest.json", out manifestPath) ||
            !artifactPaths.TryGetValue("unity_import_preset.json", out presetPath) ||
            !artifactPaths.TryGetValue("unity_animation_clip_descriptor.json", out descriptorPath) ||
            !artifactPaths.TryGetValue("animation_review.json", out reviewPath))
            throw new InvalidDataException(
                "Approved timed animation package lacks manifest, review, preset, or clip descriptor.");

        var manifest = ReadJsonFile<AnimationManifest>(manifestPath, "Animation manifest");
        var preset = ReadJsonFile<UnityImportPreset>(presetPath, "Unity import preset");
        var descriptor = ReadJsonFile<UnityAnimationClipDescriptor>(
            descriptorPath, "Unity AnimationClip descriptor");
        var review = ReadJsonFile<AnimationReview>(reviewPath, "Animation review");

        ValidateAnimationManifestContract(
            manifest, package, root, artifactPaths, artifactHashes);
        ValidateReviewContract(review, package, artifactHashes);
        ValidateUnityPresetContract(preset, manifest);
        ValidateAnimationClipDescriptorContract(
            descriptor, manifest, preset, artifactHashes);

        var expectedPaths = BuildExpectedApprovedArtifactPaths(manifest);
        var expectedCount = 5 + manifest.directions.Sum(direction => direction.frames.Count + 1);
        if (expectedPaths.Count != expectedCount)
            throw new InvalidDataException(
                "Animation manifest reuses an artifact path for more than one required source.");
        if (!expectedPaths.SetEquals(artifactPaths.Keys))
            throw new InvalidDataException(
                "Approved animation package contains unexpected or incomplete artifacts.");

        return new ValidatedAnimationPackage
        {
            Root = root,
            PackageManifestPath = packageManifestPath,
            PackageManifestSha256 = ComputeSha256(packageManifestPath),
            Package = package,
            Manifest = manifest,
            Preset = preset,
            Descriptor = descriptor,
            ArtifactPaths = artifactPaths,
            ArtifactHashes = artifactHashes
        };
    }

    private static void ValidateAnimationManifestContract(
        AnimationManifest manifest,
        ApprovedPackageManifest package,
        string root,
        Dictionary<string, string> artifactPaths,
        Dictionary<string, string> artifactHashes)
    {
        if (manifest == null || manifest.schemaVersion != "1.1" ||
            manifest.application != "Sprite Station Studio" ||
            manifest.module != "Animation Sprite Renderer")
            throw new InvalidDataException("Animation manifest contract is unsupported.");
        if (string.IsNullOrWhiteSpace(manifest.assetName) ||
            manifest.assetName != manifest.assetName.Trim() ||
            string.IsNullOrWhiteSpace(manifest.actionName) ||
            manifest.actionName != manifest.actionName.Trim())
            throw new InvalidDataException("Animation manifest asset or action identity is invalid.");
        if (manifest.canvas == null || manifest.canvas.width <= 0 || manifest.canvas.height <= 0 ||
            manifest.canvas.width > 4096 || manifest.canvas.height > 4096 ||
            !manifest.canvas.transparent || manifest.canvas.colorMode != "RGBA")
            throw new InvalidDataException("Animation manifest canvas is invalid.");
        if (manifest.normalization == null || manifest.normalization.pivot == null ||
            manifest.normalization.pivot.mode != "bottom_center" ||
            !IsNormalizedPivot(manifest.normalization.pivot.normalized))
            throw new InvalidDataException("Animation manifest normalized pivot is invalid.");
        if (manifest.frameRange == null || manifest.frameRange.start < 0 ||
            manifest.frameRange.end < manifest.frameRange.start ||
            manifest.sampledFrames == null || manifest.sampledFrames.Count == 0 ||
            manifest.sampledFrames.Count > 128)
            throw new InvalidDataException("Animation manifest sampled frame range is invalid.");
        for (var index = 0; index < manifest.sampledFrames.Count; index++)
        {
            var frame = manifest.sampledFrames[index];
            if (frame < manifest.frameRange.start || frame > manifest.frameRange.end ||
                (index > 0 && frame <= manifest.sampledFrames[index - 1]))
                throw new InvalidDataException("Animation manifest sampled frames are invalid.");
        }
        ValidateAnimationTiming(manifest.timing, manifest.sampledFrames, manifest.frameRange);
        if (manifest.directions == null || manifest.directions.Count == 0 ||
            manifest.directions.Count > 8 ||
            manifest.directionCount != manifest.directions.Count ||
            manifest.frameCountPerDirection != manifest.sampledFrames.Count ||
            package.directionCount != manifest.directionCount ||
            package.frameCountPerDirection != manifest.frameCountPerDirection)
            throw new InvalidDataException("Animation manifest direction or frame counts are inconsistent.");

        var directionIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var directionSheets = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var direction in manifest.directions)
        {
            if (direction == null || !IsSafeAssetName(direction.id) ||
                !directionIds.Add(direction.id))
                throw new InvalidDataException("Animation manifest direction ID is invalid or duplicated.");
            var sheet = ValidateSafeRelativePath(root, direction.sheet, "Animation sprite sheet");
            if (!directionSheets.Add(sheet) || !IsSha256(direction.sheetSha256))
                throw new InvalidDataException("Animation manifest sprite sheet is invalid or duplicated.");
            RequireArtifactHash(sheet, direction.sheetSha256, artifactPaths, artifactHashes);
            if (direction.frames == null ||
                direction.frames.Count != manifest.frameCountPerDirection)
                throw new InvalidDataException("Animation manifest direction frame count is invalid.");
            for (var index = 0; index < direction.frames.Count; index++)
            {
                var frame = direction.frames[index];
                if (frame == null || frame.order != index ||
                    frame.sourceFrame != manifest.sampledFrames[index] ||
                    !IsSha256(frame.sha256))
                    throw new InvalidDataException("Animation manifest frame identity is invalid.");
                var framePath = ValidateSafeRelativePath(root, frame.file, "Animation frame");
                RequireArtifactHash(framePath, frame.sha256, artifactPaths, artifactHashes);
            }
        }
        var contactSheet = ValidateSafeRelativePath(
            root, manifest.contactSheet, "Animation contact sheet");
        if (!IsSha256(manifest.contactSheetSha256))
            throw new InvalidDataException("Animation contact sheet hash is invalid.");
        RequireArtifactHash(
            contactSheet, manifest.contactSheetSha256, artifactPaths, artifactHashes);
    }

    private static void ValidateReviewContract(
        AnimationReview review,
        ApprovedPackageManifest package,
        Dictionary<string, string> artifactHashes)
    {
        if (review == null || review.schemaVersion != "1.0" ||
            review.application != "Sprite Station Studio" ||
            review.kind != "animation_review_decision" ||
            review.decision != "approved" ||
            review.animationManifest != "animation_manifest.json" ||
            !IsSha256(review.animationManifestSha256) ||
            !IsSha256(review.sourceSha256) ||
            review.animationManifestSha256 != artifactHashes["animation_manifest.json"] ||
            package.reviewSha256 != artifactHashes["animation_review.json"])
            throw new InvalidDataException("Approved animation review integrity is invalid.");
    }

    private static HashSet<string> BuildExpectedApprovedArtifactPaths(AnimationManifest manifest)
    {
        var expected = new HashSet<string>(StringComparer.Ordinal)
        {
            "animation_manifest.json",
            "animation_review.json",
            "unity_import_preset.json",
            "unity_animation_clip_descriptor.json",
            manifest.contactSheet
        };
        foreach (var direction in manifest.directions)
        {
            expected.Add(direction.sheet);
            foreach (var frame in direction.frames)
                expected.Add(frame.file);
        }
        return expected;
    }

    private static void ValidateUnityPresetContract(
        UnityImportPreset preset,
        AnimationManifest manifest)
    {
        if (preset == null || preset.schemaVersion != "1.0" || preset.engine != "Unity" ||
            preset.sourceManifestVersion != manifest.schemaVersion ||
            preset.assetName != manifest.assetName ||
            preset.applicationMode != "explicit_import")
            throw new InvalidDataException("Unity import preset contract is unsupported.");
        if (preset.assets == null || preset.assets.Count != manifest.directions.Count)
            throw new InvalidDataException("Unity import preset asset count is inconsistent.");
        ValidateMatchingTiming(preset.animationTiming, manifest.timing, "Unity import preset");

        var pivot = manifest.normalization.pivot.normalized;
        for (var directionIndex = 0; directionIndex < manifest.directions.Count; directionIndex++)
        {
            var direction = manifest.directions[directionIndex];
            var asset = preset.assets[directionIndex];
            if (asset == null || asset.file != direction.sheet || asset.name != direction.id ||
                asset.textureType != "Sprite" || asset.spriteMode != "Multiple" ||
                !asset.alphaIsTransparency || asset.mipMaps || asset.wrapMode != "Clamp" ||
                asset.filterMode != "Bilinear" || asset.compression != "Uncompressed" ||
                !NearlyEqual(asset.pixelsPerUnit, 100.0) || !PivotsEqual(asset.pivot, pivot) ||
                asset.slices == null || asset.slices.Count != direction.frames.Count)
                throw new InvalidDataException(
                    "Unity import preset does not exactly match the canonical animation asset settings.");
            for (var index = 0; index < asset.slices.Count; index++)
            {
                var slice = asset.slices[index];
                var frame = direction.frames[index];
                var expectedRect = new[]
                {
                    index * manifest.canvas.width,
                    0,
                    manifest.canvas.width,
                    manifest.canvas.height
                };
                if (slice == null || slice.name != direction.id + "_" + index.ToString("D3") ||
                    slice.sourceFrame != frame.sourceFrame || !PivotsEqual(slice.pivot, pivot) ||
                    slice.rect == null || slice.rect.Length != 4 ||
                    !slice.rect.SequenceEqual(expectedRect))
                    throw new InvalidDataException(
                        "Unity import preset sprite slice is not canonical: " + direction.id);
            }
        }
    }

    private static void ValidateAnimationClipDescriptorContract(
        UnityAnimationClipDescriptor descriptor,
        AnimationManifest manifest,
        UnityImportPreset preset,
        Dictionary<string, string> artifactHashes)
    {
        if (descriptor == null || descriptor.schemaVersion != "1.0" ||
            descriptor.application != "Sprite Station Studio" ||
            descriptor.kind != "unity_animation_clip_descriptor" ||
            descriptor.sourceAnimationManifest != "animation_manifest.json" ||
            descriptor.sourceUnityPreset != "unity_import_preset.json" ||
            descriptor.sourceAnimationManifestSha256 != artifactHashes["animation_manifest.json"] ||
            descriptor.sourceUnityPresetSha256 != artifactHashes["unity_import_preset.json"] ||
            descriptor.assetName != manifest.assetName || descriptor.actionName != manifest.actionName ||
            descriptor.clips == null || descriptor.clipCount != descriptor.clips.Count ||
            descriptor.clips.Count != manifest.directions.Count)
            throw new InvalidDataException("Unity AnimationClip descriptor identity is invalid.");

        var clipNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        for (var directionIndex = 0; directionIndex < manifest.directions.Count; directionIndex++)
        {
            var direction = manifest.directions[directionIndex];
            var asset = preset.assets[directionIndex];
            var clip = descriptor.clips[directionIndex];
            var terminalTime = manifest.timing.durationSeconds - (1.0 / manifest.timing.fps);
            var needsSyntheticTerminal = !NearlyEqual(
                manifest.timing.sampleTimesSeconds[manifest.timing.sampleTimesSeconds.Count - 1],
                terminalTime);
            var expectedKeyframeCount = manifest.sampledFrames.Count +
                (needsSyntheticTerminal ? 1 : 0);
            if (clip == null || !IsSafeAssetName(clip.name) || clip.name.Length > 128 ||
                !clipNames.Add(clip.name) || clip.directionId != direction.id ||
                clip.spriteSheet != direction.sheet ||
                clip.spriteSheetSha256 != direction.sheetSha256 ||
                clip.spriteSheetSha256 != artifactHashes[direction.sheet] ||
                !NearlyEqual(clip.frameRate, manifest.timing.fps) ||
                !NearlyEqual(clip.durationSeconds, manifest.timing.durationSeconds) ||
                clip.loopTime != (manifest.timing.loopPolicy == "loop") ||
                clip.binding == null || clip.binding.relativePath != "" ||
                clip.binding.componentType != "UnityEngine.SpriteRenderer" ||
                clip.binding.propertyName != "m_Sprite" ||
                clip.keyframes == null ||
                clip.keyframes.Count != expectedKeyframeCount)
                throw new InvalidDataException(
                    "Unity AnimationClip descriptor clip contract is invalid: " + direction.id);

            for (var index = 0; index < manifest.sampledFrames.Count; index++)
            {
                var keyframe = clip.keyframes[index];
                var slice = asset.slices[index];
                var expectedTerminal = !needsSyntheticTerminal &&
                    index == manifest.sampledFrames.Count - 1;
                if (keyframe == null || keyframe.terminal != expectedTerminal ||
                    !NearlyEqual(keyframe.timeSeconds, manifest.timing.sampleTimesSeconds[index]) ||
                    keyframe.spriteName != slice.name ||
                    keyframe.sourceFrame != manifest.sampledFrames[index])
                    throw new InvalidDataException(
                        "Unity AnimationClip descriptor keyframe is invalid: " + direction.id);
            }
            var terminal = clip.keyframes[clip.keyframes.Count - 1];
            if (terminal == null || !terminal.terminal ||
                !NearlyEqual(terminal.timeSeconds, terminalTime) ||
                terminal.spriteName != asset.slices[asset.slices.Count - 1].name ||
                terminal.sourceFrame != manifest.sampledFrames[manifest.sampledFrames.Count - 1])
                throw new InvalidDataException(
                    "Unity AnimationClip descriptor terminal keyframe is invalid: " + direction.id);
            if (needsSyntheticTerminal &&
                terminal.timeSeconds <= clip.keyframes[clip.keyframes.Count - 2].timeSeconds)
                throw new InvalidDataException(
                    "Unity AnimationClip synthetic terminal keyframe is invalid: " + direction.id);
        }
    }

    private static void ValidateAnimationTiming(
        AnimationTiming timing,
        List<int> sampledFrames,
        AnimationFrameRange frameRange)
    {
        if (timing == null || !IsFinitePositive(timing.fps) || timing.fps > 240.0 ||
            (timing.fpsSource != "scene" && timing.fpsSource != "override") ||
            timing.sourceFrameStep <= 0 ||
            timing.sampleTimesSeconds == null ||
            timing.sampleTimesSeconds.Count != sampledFrames.Count ||
            !IsFinitePositive(timing.durationSeconds) || timing.durationSeconds > 86400.0 ||
            (timing.loopPolicy != "once" && timing.loopPolicy != "loop"))
            throw new InvalidDataException("Animation timing contract is invalid.");
        for (var index = 0; index < timing.sampleTimesSeconds.Count; index++)
        {
            var time = timing.sampleTimesSeconds[index];
            if (!IsFiniteNonNegative(time) ||
                (index == 0 && !NearlyEqual(time, 0.0)) ||
                (index > 0 && time <= timing.sampleTimesSeconds[index - 1]))
                throw new InvalidDataException("Animation sample times are invalid.");
        }
        if (timing.durationSeconds <= timing.sampleTimesSeconds[timing.sampleTimesSeconds.Count - 1])
            throw new InvalidDataException("Animation duration must follow the final sampled frame.");
        for (var index = 0; index < sampledFrames.Count; index++)
        {
            var expectedTime = (sampledFrames[index] - frameRange.start) / timing.fps;
            if (!NearlyEqual(timing.sampleTimesSeconds[index], expectedTime))
                throw new InvalidDataException("Animation timing does not match sampled frames.");
        }
        var expectedDuration = (frameRange.end - frameRange.start + 1) / timing.fps;
        if (!NearlyEqual(timing.durationSeconds, expectedDuration))
            throw new InvalidDataException("Animation duration does not match the frame range.");
        for (var index = 1; index < sampledFrames.Count; index++)
            if (sampledFrames[index] - sampledFrames[index - 1] != timing.sourceFrameStep)
                throw new InvalidDataException("Animation source frame step is inconsistent.");
    }

    private static void ValidateMatchingTiming(
        AnimationTiming actual,
        AnimationTiming expected,
        string label)
    {
        if (actual == null || expected == null ||
            !NearlyEqual(actual.fps, expected.fps) || actual.fpsSource != expected.fpsSource ||
            actual.sourceFrameStep != expected.sourceFrameStep ||
            !NearlyEqual(actual.durationSeconds, expected.durationSeconds) ||
            actual.loopPolicy != expected.loopPolicy ||
            actual.sampleTimesSeconds == null || expected.sampleTimesSeconds == null ||
            actual.sampleTimesSeconds.Count != expected.sampleTimesSeconds.Count)
            throw new InvalidDataException(label + " timing does not match the animation manifest.");
        for (var index = 0; index < actual.sampleTimesSeconds.Count; index++)
            if (!NearlyEqual(actual.sampleTimesSeconds[index], expected.sampleTimesSeconds[index]))
                throw new InvalidDataException(label + " sample times do not match the animation manifest.");
    }

    private static void CreateAnimationJobAssets(
        ValidatedAnimationPackage package,
        string projectRoot)
    {
        var jobAbsolute = AssetPathToAbsolute(projectRoot, AnimationJobRoot);
        Directory.CreateDirectory(AssetPathToAbsolute(projectRoot, AnimationSheetsRoot));
        Directory.CreateDirectory(AssetPathToAbsolute(projectRoot, AnimationClipsRoot));

        for (var index = 0; index < package.Manifest.directions.Count; index++)
        {
            var direction = package.Manifest.directions[index];
            var presetAsset = package.Preset.assets[index];
            var source = package.ArtifactPaths[direction.sheet];
            var destinationAssetPath = SheetAssetPath(direction.id);
            var destination = AssetPathToAbsolute(projectRoot, destinationAssetPath);
            if (File.Exists(destination) || File.Exists(destination + ".meta"))
                throw new IOException("Generated sprite sheet already exists: " + destinationAssetPath);
            File.Copy(source, destination, false);
            if (ComputeSha256(destination) != direction.sheetSha256)
                throw new InvalidDataException("Copied sprite sheet hash mismatch: " + direction.id);
            ImportAnimationSpriteSheet(destinationAssetPath, presetAsset, package.Manifest.canvas);
        }

        var spriteMaps = LoadAndVerifyAllSpriteSheets(package);
        for (var index = 0; index < package.Descriptor.clips.Count; index++)
        {
            var descriptor = package.Descriptor.clips[index];
            Dictionary<string, Sprite> sprites;
            if (!spriteMaps.TryGetValue(descriptor.directionId, out sprites))
                throw new InvalidDataException(
                    "Imported sprite sheet is missing for clip: " + descriptor.name);
            var clip = new AnimationClip
            {
                name = descriptor.name,
                frameRate = (float)descriptor.frameRate
            };
            var keyframes = new ObjectReferenceKeyframe[descriptor.keyframes.Count];
            for (var keyIndex = 0; keyIndex < descriptor.keyframes.Count; keyIndex++)
            {
                var expected = descriptor.keyframes[keyIndex];
                Sprite sprite;
                if (!sprites.TryGetValue(expected.spriteName, out sprite))
                    throw new InvalidDataException(
                        "Imported sprite is missing: " + expected.spriteName);
                keyframes[keyIndex] = new ObjectReferenceKeyframe
                {
                    time = (float)expected.timeSeconds,
                    value = sprite
                };
            }
            var binding = new EditorCurveBinding
            {
                path = descriptor.binding.relativePath,
                type = typeof(SpriteRenderer),
                propertyName = descriptor.binding.propertyName
            };
            AnimationUtility.SetObjectReferenceCurve(clip, binding, keyframes);
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            settings.loopTime = descriptor.loopTime;
            settings.loopBlend = false;
            settings.loopBlendOrientation = false;
            settings.loopBlendPositionY = false;
            settings.loopBlendPositionXZ = false;
            AnimationUtility.SetAnimationClipSettings(clip, settings);

            var clipAssetPath = ClipAssetPath(descriptor.name);
            var clipAbsolute = AssetPathToAbsolute(projectRoot, clipAssetPath);
            if (File.Exists(clipAbsolute) || File.Exists(clipAbsolute + ".meta") ||
                AssetDatabase.LoadMainAssetAtPath(clipAssetPath) != null)
                throw new IOException("Generated animation clip already exists: " + clipAssetPath);
            AssetDatabase.CreateAsset(clip, clipAssetPath);
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        if (!Directory.Exists(jobAbsolute))
            throw new IOException("Unity did not create the generated animation asset root.");
    }

    private static void ImportAnimationSpriteSheet(
        string assetPath,
        SpriteImportAsset asset,
        AnimationCanvas canvas)
    {
        AssetDatabase.ImportAsset(
            assetPath,
            ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
        if (importer == null)
            throw new InvalidDataException("Generated sprite sheet has no TextureImporter: " + assetPath);

        importer.textureType = TextureImporterType.Sprite;
        importer.spriteImportMode = SpriteImportMode.Multiple;
        importer.alphaIsTransparency = asset.alphaIsTransparency;
        importer.mipmapEnabled = asset.mipMaps;
        importer.wrapMode = TextureWrapMode.Clamp;
        importer.filterMode = FilterMode.Bilinear;
        importer.textureCompression = TextureImporterCompression.Uncompressed;
        importer.spritePixelsPerUnit = asset.pixelsPerUnit;
        var textureSettings = new TextureImporterSettings();
        importer.ReadTextureSettings(textureSettings);
        textureSettings.spriteAlignment = (int)SpriteAlignment.Custom;
        textureSettings.spritePivot = new Vector2(asset.pivot[0], asset.pivot[1]);
        importer.SetTextureSettings(textureSettings);
        importer.SaveAndReimport();

        var factory = new SpriteDataProviderFactories();
        factory.Init();
        var provider = factory.GetSpriteEditorDataProviderFromObject(importer);
        if (provider == null)
            throw new InvalidDataException("Unity Sprite data provider is unavailable: " + assetPath);
        provider.InitSpriteEditorDataProvider();
        var spriteRects = asset.slices.Select(slice => new SpriteRect
        {
            name = slice.name,
            rect = new Rect(slice.rect[0], slice.rect[1], slice.rect[2], slice.rect[3]),
            alignment = SpriteAlignment.Custom,
            pivot = new Vector2(slice.pivot[0], slice.pivot[1]),
            spriteID = GUID.Generate()
        }).ToArray();
        provider.SetSpriteRects(spriteRects);
        provider.Apply();
        importer.SaveAndReimport();

        var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(assetPath);
        if (texture == null || texture.width != canvas.width * asset.slices.Count ||
            texture.height != canvas.height)
            throw new InvalidDataException(
                "Generated sprite sheet dimensions do not match canonical slices: " + assetPath);
    }

    private static Dictionary<string, Dictionary<string, Sprite>> LoadAndVerifyAllSpriteSheets(
        ValidatedAnimationPackage package)
    {
        var result = new Dictionary<string, Dictionary<string, Sprite>>(StringComparer.Ordinal);
        for (var index = 0; index < package.Manifest.directions.Count; index++)
        {
            var direction = package.Manifest.directions[index];
            var presetAsset = package.Preset.assets[index];
            var assetPath = SheetAssetPath(direction.id);
            VerifyTextureImporter(assetPath, presetAsset);
            var sprites = AssetDatabase.LoadAllAssetsAtPath(assetPath)
                .OfType<Sprite>()
                .ToArray();
            if (sprites.Length != presetAsset.slices.Count)
                throw new InvalidDataException(
                    "Imported sprite count does not match preset: " + assetPath);
            var spriteMap = new Dictionary<string, Sprite>(StringComparer.Ordinal);
            var insensitiveNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var sprite in sprites)
            {
                if (!insensitiveNames.Add(sprite.name) || !spriteMap.TryAdd(sprite.name, sprite))
                    throw new InvalidDataException(
                        "Imported sprite names are duplicated, including case-only duplicates: " + assetPath);
            }
            if (!new HashSet<string>(
                presetAsset.slices.Select(slice => slice.name),
                StringComparer.Ordinal).SetEquals(spriteMap.Keys))
                throw new InvalidDataException("Imported sprite names do not match preset: " + assetPath);
            result.Add(direction.id, spriteMap);
        }
        return result;
    }

    private static void VerifyTextureImporter(string assetPath, SpriteImportAsset expected)
    {
        var importer = AssetImporter.GetAtPath(assetPath) as TextureImporter;
        if (importer == null || importer.textureType != TextureImporterType.Sprite ||
            importer.spriteImportMode != SpriteImportMode.Multiple ||
            importer.alphaIsTransparency != expected.alphaIsTransparency ||
            importer.mipmapEnabled != expected.mipMaps || importer.wrapMode != TextureWrapMode.Clamp ||
            importer.filterMode != FilterMode.Bilinear ||
            importer.textureCompression != TextureImporterCompression.Uncompressed ||
            !NearlyEqual(importer.spritePixelsPerUnit, expected.pixelsPerUnit))
            throw new InvalidDataException("Imported texture settings do not match preset: " + assetPath);

        var textureSettings = new TextureImporterSettings();
        importer.ReadTextureSettings(textureSettings);
        if (textureSettings.spriteAlignment != (int)SpriteAlignment.Custom ||
            !NearlyEqual(textureSettings.spritePivot.x, expected.pivot[0]) ||
            !NearlyEqual(textureSettings.spritePivot.y, expected.pivot[1]))
            throw new InvalidDataException("Imported texture pivot does not match preset: " + assetPath);

        var factory = new SpriteDataProviderFactories();
        factory.Init();
        var provider = factory.GetSpriteEditorDataProviderFromObject(importer);
        if (provider == null)
            throw new InvalidDataException("Unity Sprite data provider is unavailable: " + assetPath);
        provider.InitSpriteEditorDataProvider();
        var actualRects = provider.GetSpriteRects();
        if (actualRects == null || actualRects.Length != expected.slices.Count)
            throw new InvalidDataException("Imported sprite slice count does not match preset: " + assetPath);
        var rectsByName = new Dictionary<string, SpriteRect>(StringComparer.Ordinal);
        var insensitiveNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var rect in actualRects)
            if (!insensitiveNames.Add(rect.name) || !rectsByName.TryAdd(rect.name, rect))
                throw new InvalidDataException("Imported sprite slice names are duplicated: " + assetPath);
        foreach (var slice in expected.slices)
        {
            SpriteRect actual;
            if (!rectsByName.TryGetValue(slice.name, out actual) ||
                !NearlyEqual(actual.rect.x, slice.rect[0]) ||
                !NearlyEqual(actual.rect.y, slice.rect[1]) ||
                !NearlyEqual(actual.rect.width, slice.rect[2]) ||
                !NearlyEqual(actual.rect.height, slice.rect[3]) ||
                actual.alignment != SpriteAlignment.Custom ||
                !NearlyEqual(actual.pivot.x, slice.pivot[0]) ||
                !NearlyEqual(actual.pivot.y, slice.pivot[1]))
                throw new InvalidDataException(
                    "Imported sprite slice rect or pivot does not match preset: " + slice.name);
        }
    }

    private static AnimationJobVerification VerifyAnimationJob(
        ValidatedAnimationPackage package,
        string projectRoot)
    {
        var spriteMaps = LoadAndVerifyAllSpriteSheets(package);
        var identities = new Dictionary<string, SpriteIdentity>(StringComparer.Ordinal);
        foreach (var direction in package.Manifest.directions)
        {
            foreach (var pair in spriteMaps[direction.id])
            {
                string guid;
                long localId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(pair.Value, out guid, out localId) ||
                    string.IsNullOrWhiteSpace(guid) || localId == 0)
                    throw new InvalidDataException("Unity did not assign a stable sprite identity: " + pair.Key);
                identities.Add(direction.id + "\n" + pair.Key, new SpriteIdentity
                {
                    Guid = guid,
                    LocalId = localId
                });
            }
        }

        var reports = new List<AnimationBuildClipReport>();
        foreach (var expected in package.Descriptor.clips)
        {
            var assetPath = ClipAssetPath(expected.name);
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(assetPath);
            if (clip == null)
                throw new InvalidDataException("Generated AnimationClip cannot be loaded: " + assetPath);
            if (clip.name != expected.name)
                throw new InvalidDataException(
                    "Generated AnimationClip name is invalid: " + clip.name + " != " + expected.name);
            if (!NearlyEqual(clip.frameRate, expected.frameRate))
                throw new InvalidDataException(
                    "Generated AnimationClip frame rate is invalid: " + clip.frameRate +
                    " != " + expected.frameRate + " (" + expected.name + ")");
            if (!NearlyEqual(clip.length, expected.durationSeconds))
                throw new InvalidDataException(
                    "Generated AnimationClip length is invalid: " + clip.length +
                    " != " + expected.durationSeconds + " (" + expected.name + ")");

            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            if (settings.loopTime != expected.loopTime || settings.loopBlend ||
                settings.loopBlendOrientation || settings.loopBlendPositionY ||
                settings.loopBlendPositionXZ)
                throw new InvalidDataException("Generated AnimationClip loop settings are invalid: " + expected.name);
            if (AnimationUtility.GetCurveBindings(clip).Length != 0)
                throw new InvalidDataException("Generated AnimationClip contains unexpected numeric curves: " + expected.name);
            if (AnimationUtility.GetAnimationEvents(clip).Length != 0)
                throw new InvalidDataException("Generated AnimationClip contains unexpected events: " + expected.name);

            var bindings = AnimationUtility.GetObjectReferenceCurveBindings(clip);
            if (bindings.Length != 1 || bindings[0].path != expected.binding.relativePath ||
                bindings[0].type != typeof(SpriteRenderer) ||
                bindings[0].propertyName != expected.binding.propertyName)
                throw new InvalidDataException("Generated AnimationClip binding is invalid: " + expected.name);
            var actualKeys = AnimationUtility.GetObjectReferenceCurve(clip, bindings[0]);
            if (actualKeys == null || actualKeys.Length != expected.keyframes.Count)
                throw new InvalidDataException("Generated AnimationClip keyframe count is invalid: " + expected.name);

            var clipReport = new AnimationBuildClipReport
            {
                name = expected.name,
                assetPath = assetPath,
                frameRate = expected.frameRate,
                durationSeconds = expected.durationSeconds,
                loopTime = expected.loopTime,
                binding = new AnimationClipBindingDescriptor
                {
                    relativePath = expected.binding.relativePath,
                    componentType = expected.binding.componentType,
                    propertyName = expected.binding.propertyName
                }
            };
            for (var index = 0; index < actualKeys.Length; index++)
            {
                var actual = actualKeys[index];
                var expectedKey = expected.keyframes[index];
                var sprite = actual.value as Sprite;
                if (!NearlyEqual(actual.time, expectedKey.timeSeconds) || sprite == null ||
                    sprite.name != expectedKey.spriteName)
                    throw new InvalidDataException(
                        "Generated AnimationClip keyframe does not match descriptor: " + expected.name);
                string guid;
                long localId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprite, out guid, out localId) ||
                    string.IsNullOrWhiteSpace(guid) || localId == 0)
                    throw new InvalidDataException(
                        "Generated AnimationClip sprite identity is invalid: " + expectedKey.spriteName);
                Sprite expectedSprite;
                if (!spriteMaps[expected.directionId].TryGetValue(expectedKey.spriteName, out expectedSprite) ||
                    expectedSprite != sprite)
                    throw new InvalidDataException(
                        "Generated AnimationClip references a sprite from an unexpected sheet: " + expected.name);
                clipReport.keyframes.Add(new AnimationBuildKeyframeReport
                {
                    timeSeconds = expectedKey.timeSeconds,
                    spriteName = expectedKey.spriteName,
                    sourceFrame = expectedKey.sourceFrame,
                    terminal = expectedKey.terminal,
                    spriteGuid = guid,
                    spriteLocalId = localId
                });
            }
            reports.Add(clipReport);
        }

        VerifyGeneratedAssetFileSet(package, projectRoot);
        return new AnimationJobVerification
        {
            Clips = reports,
            SpriteIdentities = identities
        };
    }

    private static void VerifyGeneratedAssetFileSet(
        ValidatedAnimationPackage package,
        string projectRoot)
    {
        var expected = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var direction in package.Manifest.directions)
        {
            var sheet = SheetAssetPath(direction.id);
            expected.Add(sheet);
            expected.Add(sheet + ".meta");
        }
        foreach (var clip in package.Descriptor.clips)
        {
            var path = ClipAssetPath(clip.name);
            expected.Add(path);
            expected.Add(path + ".meta");
        }
        expected.Add(AnimationJobRoot + "/Sheets.meta");
        expected.Add(AnimationJobRoot + "/Clips.meta");

        var jobAbsolute = AssetPathToAbsolute(projectRoot, AnimationJobRoot);
        var actual = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var file in Directory.GetFiles(jobAbsolute, "*", SearchOption.AllDirectories))
        {
            var relative = AnimationJobRoot + "/" +
                Path.GetRelativePath(jobAbsolute, file).Replace('\\', '/');
            if (!actual.Add(relative))
                throw new InvalidDataException(
                    "Generated animation job contains case-insensitive duplicate files.");
        }
        if (!actual.SetEquals(expected))
            throw new InvalidDataException(
                "Generated animation job contains missing or unexpected files.");
    }

    private static void VerifyStableSpriteIdentities(
        AnimationJobVerification before,
        AnimationJobVerification after)
    {
        if (before.SpriteIdentities.Count != after.SpriteIdentities.Count)
            throw new InvalidDataException("Portable reload changed the number of sprite identities.");
        foreach (var pair in before.SpriteIdentities)
        {
            SpriteIdentity restored;
            if (!after.SpriteIdentities.TryGetValue(pair.Key, out restored) ||
                pair.Value.Guid != restored.Guid || pair.Value.LocalId != restored.LocalId)
                throw new InvalidDataException(
                    "Portable reload did not preserve sprite GUID/local ID: " + pair.Key.Replace("\n", "/"));
        }
    }

    private static Dictionary<string, string> PreservePortableAssetPairs(
        ValidatedAnimationPackage package,
        string projectRoot,
        string portabilityDirectory)
    {
        var hashes = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var assetPath in GetGeneratedDataAssetPaths(package))
        {
            foreach (var path in new[] { assetPath, assetPath + ".meta" })
            {
                var source = AssetPathToAbsolute(projectRoot, path);
                if (!File.Exists(source))
                    throw new FileNotFoundException("Portable asset pair is incomplete.", source);
                var relative = path.Substring((AnimationJobRoot + "/").Length);
                var destination = Path.Combine(
                    portabilityDirectory, relative.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(destination));
                File.Copy(source, destination, false);
                var hash = ComputeSha256(source);
                if (ComputeSha256(destination) != hash)
                    throw new IOException("Portable asset copy hash mismatch: " + path);
                hashes.Add(path, hash);
            }
        }
        return hashes;
    }

    private static void RestorePortableAssetPairs(
        ValidatedAnimationPackage package,
        string projectRoot,
        string portabilityDirectory,
        Dictionary<string, string> preservedHashes)
    {
        Directory.CreateDirectory(AssetPathToAbsolute(projectRoot, AnimationSheetsRoot));
        Directory.CreateDirectory(AssetPathToAbsolute(projectRoot, AnimationClipsRoot));
        foreach (var assetPath in GetGeneratedDataAssetPaths(package))
        {
            foreach (var path in new[] { assetPath, assetPath + ".meta" })
            {
                var relative = path.Substring((AnimationJobRoot + "/").Length);
                var source = Path.Combine(
                    portabilityDirectory, relative.Replace('/', Path.DirectorySeparatorChar));
                var destination = AssetPathToAbsolute(projectRoot, path);
                if (File.Exists(destination))
                    throw new IOException("Portable reload would overwrite an asset: " + path);
                File.Copy(source, destination, false);
                if (ComputeSha256(destination) != preservedHashes[path])
                    throw new IOException("Portable reload changed asset bytes: " + path);
            }
        }
    }

    private static void VerifyRestoredAssetPairHashes(
        string projectRoot,
        Dictionary<string, string> preservedHashes)
    {
        foreach (var pair in preservedHashes)
        {
            var absolute = AssetPathToAbsolute(projectRoot, pair.Key);
            if (!File.Exists(absolute) || ComputeSha256(absolute) != pair.Value)
                throw new IOException(
                    "Portable reload did not preserve generated asset bytes: " + pair.Key);
        }
    }

    private static List<string> GetGeneratedDataAssetPaths(ValidatedAnimationPackage package)
    {
        var paths = package.Manifest.directions
            .Select(direction => SheetAssetPath(direction.id))
            .Concat(package.Descriptor.clips.Select(clip => ClipAssetPath(clip.name)))
            .ToList();
        if (paths.Count != paths.Distinct(StringComparer.OrdinalIgnoreCase).Count())
            throw new InvalidDataException("Generated asset paths contain case-insensitive duplicates.");
        return paths;
    }

    private static AnimationClipBuildReport BuildAnimationClipReport(
        ValidatedAnimationPackage package,
        string projectRoot,
        AnimationJobVerification verification)
    {
        var report = new AnimationClipBuildReport
        {
            unityVersion = Application.unityVersion,
            sourcePackageSha256 = package.PackageManifestSha256,
            portableReloadVerified = true,
            clipCount = package.Descriptor.clips.Count,
            spriteSheetCount = package.Manifest.directions.Count,
            keyframeCount = package.Descriptor.clips.Sum(clip => clip.keyframes.Count),
            clips = verification.Clips
        };
        foreach (var direction in package.Manifest.directions)
        {
            AddAnimationBuildFile(
                report, projectRoot, SheetAssetPath(direction.id), "sprite_sheet");
            AddAnimationBuildFile(
                report, projectRoot, SheetAssetPath(direction.id) + ".meta", "sprite_sheet_meta");
        }
        foreach (var clip in package.Descriptor.clips)
        {
            AddAnimationBuildFile(
                report, projectRoot, ClipAssetPath(clip.name), "animation_clip");
            AddAnimationBuildFile(
                report, projectRoot, ClipAssetPath(clip.name) + ".meta", "animation_clip_meta");
        }
        return report;
    }

    private static void AddAnimationBuildFile(
        AnimationClipBuildReport report,
        string projectRoot,
        string assetPath,
        string role)
    {
        var absolute = AssetPathToAbsolute(projectRoot, assetPath);
        if (!File.Exists(absolute))
            throw new FileNotFoundException("Generated report file is missing.", absolute);
        report.files.Add(new AnimationBuildFileReport
        {
            path = assetPath.Substring((AnimationJobRoot + "/").Length),
            sha256 = ComputeSha256(absolute),
            role = role
        });
    }

    private static void WriteAnimationClipBuildReport(
        string path,
        AnimationClipBuildReport report)
    {
        var parent = Path.GetDirectoryName(path);
        if (string.IsNullOrEmpty(parent))
            throw new InvalidDataException("Animation clip report directory is invalid.");
        Directory.CreateDirectory(parent);
        using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        using (var writer = new StreamWriter(stream, new UTF8Encoding(false)))
        {
            writer.NewLine = "\n";
            writer.Write(JsonUtility.ToJson(report, true));
            writer.Write("\n");
            writer.Flush();
            stream.Flush(true);
        }
        Debug.Log("Sprite Station Unity animation clip report written: " + path);
    }

    private static void VerifyPackageFilesUnchanged(ValidatedAnimationPackage package)
    {
        if (ComputeSha256(package.PackageManifestPath) != package.PackageManifestSha256)
            throw new InvalidDataException("Approved package manifest changed during Unity processing.");
        foreach (var pair in package.ArtifactPaths)
            if (!File.Exists(pair.Value) || ComputeSha256(pair.Value) != package.ArtifactHashes[pair.Key])
                throw new InvalidDataException(
                    "Approved package artifact changed during Unity processing: " + pair.Key);
    }

    private static void DeleteAnimationJobBestEffort(string jobAbsolute)
    {
        try
        {
            AssetDatabase.DeleteAsset(AnimationJobRoot);
            AssetDatabase.Refresh(
                ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
        }
        catch { }
        try
        {
            if (Directory.Exists(jobAbsolute))
                Directory.Delete(jobAbsolute, true);
            if (File.Exists(jobAbsolute + ".meta"))
                File.Delete(jobAbsolute + ".meta");
        }
        catch { }
    }

    private static string SheetAssetPath(string directionId)
    {
        return AnimationSheetsRoot + "/" + directionId + ".png";
    }

    private static string ClipAssetPath(string clipName)
    {
        return AnimationClipsRoot + "/" + clipName + ".anim";
    }

    private static string AssetPathToAbsolute(string projectRoot, string assetPath)
    {
        if (string.IsNullOrWhiteSpace(assetPath) ||
            !assetPath.StartsWith("Assets/", StringComparison.Ordinal) ||
            assetPath.Contains("\\") || assetPath.Contains(".."))
            throw new InvalidDataException("Unity asset path is unsafe: " + assetPath);
        var absolute = Path.GetFullPath(Path.Combine(
            projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar)));
        var assetsRoot = Path.GetFullPath(Application.dataPath);
        var assetsPrefix = assetsRoot.TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!absolute.StartsWith(assetsPrefix, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Unity asset path escapes Assets: " + assetPath);
        return absolute;
    }

    private static T ReadJsonFile<T>(string path, string label) where T : class
    {
        try
        {
            var value = JsonUtility.FromJson<T>(File.ReadAllText(path, Encoding.UTF8));
            if (value == null)
                throw new InvalidDataException(label + " must be a JSON object.");
            return value;
        }
        catch (Exception exception) when (
            exception is IOException || exception is UnauthorizedAccessException ||
            exception is ArgumentException)
        {
            throw new InvalidDataException("Cannot read " + label + ": " + exception.Message, exception);
        }
    }

    private static string ValidateSafeRelativePath(string root, string value, string label)
    {
        if (string.IsNullOrWhiteSpace(value) || value != value.Trim() ||
            Path.IsPathRooted(value) || value.Contains("\\") || value.Contains(":") ||
            value.StartsWith("/", StringComparison.Ordinal) ||
            value.EndsWith("/", StringComparison.Ordinal))
            throw new InvalidDataException(label + " path must be a canonical relative path.");
        var segments = value.Split('/');
        if (segments.Any(segment => string.IsNullOrEmpty(segment) || segment == "." ||
            segment == ".." || segment.EndsWith(".", StringComparison.Ordinal) ||
            segment.EndsWith(" ", StringComparison.Ordinal)))
            throw new InvalidDataException(label + " path contains an unsafe segment.");
        var absolute = Path.GetFullPath(Path.Combine(
            root, value.Replace('/', Path.DirectorySeparatorChar)));
        var prefix = Path.GetFullPath(root).TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!absolute.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ||
            Path.GetRelativePath(root, absolute).Replace('\\', '/') != value)
            throw new InvalidDataException(label + " path escapes or is not canonical.");
        return value;
    }

    private static void RequireArtifactHash(
        string relative,
        string expectedHash,
        Dictionary<string, string> artifactPaths,
        Dictionary<string, string> artifactHashes)
    {
        if (!artifactPaths.ContainsKey(relative) ||
            !artifactHashes.TryGetValue(relative, out var hash) || hash != expectedHash)
            throw new InvalidDataException(
                "Approved package does not hash-bind required artifact: " + relative);
    }

    private static void RejectReparsePoint(string path, string label)
    {
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException(label + " cannot be a symbolic link or reparse point: " + path);
    }

    private static bool IsSha256(string value)
    {
        return value != null && value.Length == 64 &&
            value.All(character => (character >= '0' && character <= '9') ||
                                   (character >= 'a' && character <= 'f'));
    }

    private static string ComputeSha256(string path)
    {
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        using (var sha = SHA256.Create())
            return string.Concat(sha.ComputeHash(stream).Select(value => value.ToString("x2")));
    }

    private static bool IsSafeAssetName(string value)
    {
        if (string.IsNullOrWhiteSpace(value) || value != value.Trim() || value == "." || value == ".." ||
            value.Length > 128 || value.EndsWith(".", StringComparison.Ordinal) ||
            value.EndsWith(" ", StringComparison.Ordinal))
            return false;
        var invalid = Path.GetInvalidFileNameChars();
        return value.All(character => character >= 0x20 && character != 0x7f &&
                                      character != '/' && character != '\\' &&
                                      !invalid.Contains(character));
    }

    private static bool IsNormalizedPivot(float[] pivot)
    {
        return pivot != null && pivot.Length == 2 &&
            !float.IsNaN(pivot[0]) && !float.IsInfinity(pivot[0]) &&
            !float.IsNaN(pivot[1]) && !float.IsInfinity(pivot[1]) &&
            pivot[0] >= 0f && pivot[0] <= 1f && pivot[1] >= 0f && pivot[1] <= 1f;
    }

    private static bool PivotsEqual(float[] first, float[] second)
    {
        return IsNormalizedPivot(first) && IsNormalizedPivot(second) &&
            NearlyEqual(first[0], second[0]) && NearlyEqual(first[1], second[1]);
    }

    private static bool IsFinitePositive(double value)
    {
        return !double.IsNaN(value) && !double.IsInfinity(value) && value > 0.0;
    }

    private static bool IsFiniteNonNegative(double value)
    {
        return !double.IsNaN(value) && !double.IsInfinity(value) && value >= 0.0;
    }

    private static bool NearlyEqual(double first, double second)
    {
        return Math.Abs(first - second) <= 0.00001;
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
