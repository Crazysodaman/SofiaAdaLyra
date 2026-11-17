using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace Aegis.Setup
{
    internal static class AegisSetupLauncher
    {
        private const string InstallerName = "Install-Aegis.ps1";

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                string baseDirectory = AppDomain.CurrentDomain.BaseDirectory;
                string installer = FindInstaller(baseDirectory);
                string bundleRoot = FindBundleRoot(baseDirectory, installer);
                if (installer == null)
                {
                    return Fail(
                        "Aegis setup media is incomplete: Install-Aegis.ps1 was not found " +
                        "next to Aegis-Setup.exe or in the adjacent installer directory. " +
                        "Use the complete signed setup media.");
                }
                if (bundleRoot == null)
                {
                    return Fail(
                        "Aegis setup media is incomplete: release-manifest.json was not found " +
                        "next to Aegis-Setup.exe, in its parent directory, or in ./release or " +
                        "./bundle. Use the complete signed setup media.");
                }

                string powershell = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.System),
                    "WindowsPowerShell", "v1.0", "powershell.exe");
                if (!File.Exists(powershell))
                {
                    powershell = "powershell.exe";
                }

                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = powershell;
                start.Arguments = "-NoProfile -File " + Quote(installer) +
                    " -BundleRoot " + Quote(bundleRoot) + Forward(args);
                start.WorkingDirectory = bundleRoot;
                start.UseShellExecute = true;
                start.Verb = "runas";
                start.WindowStyle = ProcessWindowStyle.Normal;

                using (Process process = Process.Start(start))
                {
                    if (process == null)
                    {
                        return Fail("Windows did not start the elevated Aegis installer.");
                    }
                    process.WaitForExit();
                    int exitCode = process.ExitCode;
                    if (exitCode != 0)
                    {
                        MessageBox.Show(
                            "Aegis setup did not complete. The guided installer exited with code " +
                            exitCode + ". Review the installer window for the exact failed step. " +
                            "Setup did not retry or hide a failed step.",
                            "Aegis Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                    return exitCode;
                }
            }
            catch (Win32Exception error)
            {
                if (error.NativeErrorCode == 1223)
                {
                    return Fail("Administrator approval was cancelled. Run Aegis-Setup.exe again " +
                        "and approve the Windows UAC prompt.");
                }
                return Fail("Windows could not start the elevated Aegis installer: " + error.Message);
            }
            catch (Exception error)
            {
                return Fail("Aegis setup launcher failed: " + error.Message);
            }
        }

        private static string FindInstaller(string baseDirectory)
        {
            string[] candidates = new string[]
            {
                Path.Combine(baseDirectory, InstallerName),
                Path.Combine(baseDirectory, "installer", InstallerName),
                Path.Combine(Directory.GetParent(baseDirectory) == null
                    ? baseDirectory
                    : Directory.GetParent(baseDirectory).FullName, InstallerName)
            };
            foreach (string candidate in candidates)
            {
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
            return null;
        }

        private static string FindBundleRoot(string baseDirectory, string installer)
        {
            string parent = Directory.GetParent(baseDirectory) == null
                ? baseDirectory
                : Directory.GetParent(baseDirectory).FullName;
            string[] candidates = new string[]
            {
                baseDirectory,
                parent,
                Path.Combine(baseDirectory, "release"),
                Path.Combine(baseDirectory, "bundle")
            };
            foreach (string candidate in candidates)
            {
                if (File.Exists(Path.Combine(candidate, "release-manifest.json")))
                {
                    return candidate;
                }
            }
            if (installer != null)
            {
                string installerDirectory = Path.GetDirectoryName(installer);
                string installerParent = Directory.GetParent(installerDirectory) == null
                    ? installerDirectory
                    : Directory.GetParent(installerDirectory).FullName;
                if (File.Exists(Path.Combine(installerParent, "release-manifest.json")))
                {
                    return installerParent;
                }
            }
            return null;
        }

        private static string Forward(string[] args)
        {
            if (args == null || args.Length == 0)
            {
                return string.Empty;
            }
            System.Text.StringBuilder builder = new System.Text.StringBuilder();
            foreach (string argument in args)
            {
                if (argument == null || argument.IndexOf('"') >= 0 ||
                    argument.IndexOf('\r') >= 0 || argument.IndexOf('\n') >= 0)
                {
                    throw new ArgumentException("Unsupported setup argument.");
                }
                builder.Append(' ').Append(Quote(argument));
            }
            return builder.ToString();
        }

        private static string Quote(string value)
        {
            if (value.IndexOf('"') >= 0 || value.IndexOf('\r') >= 0 || value.IndexOf('\n') >= 0)
            {
                throw new ArgumentException("Unsupported setup path.");
            }
            return "\"" + value + "\"";
        }

        private static int Fail(string message)
        {
            MessageBox.Show(message, "Aegis Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
    }
}
