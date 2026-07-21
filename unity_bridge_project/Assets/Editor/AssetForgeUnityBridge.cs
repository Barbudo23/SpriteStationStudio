using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class AssetForgeUnityBridge
{
    [Serializable]
    private sealed class Command
    {
        public string operation;
        public string sourcePath;
        public string reportPath;
        public string workingAssetPath = "Assets/AssetForgeInput";
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
                throw new FileNotFoundException("AssetForge command JSON not found.", commandPath);

            var command = JsonUtility.FromJson<Command>(File.ReadAllText(commandPath));
            report.operation = command.operation;
            report.sourcePath = command.sourcePath;

            if (command.operation == "ping")
            {
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

    private static void AnalyzeAsset(Command command, AssetReport report)
    {
        if (string.IsNullOrWhiteSpace(command.sourcePath) || !File.Exists(command.sourcePath))
            throw new FileNotFoundException("Source asset not found.", command.sourcePath);

        var folder = string.IsNullOrWhiteSpace(command.workingAssetPath)
            ? "Assets/AssetForgeInput"
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
        Debug.Log("AssetForge Unity report written: " + absolute);
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
