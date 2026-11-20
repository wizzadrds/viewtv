# VIEWTV 0013 — Restricted Windows impersonation token (test only).
# Does not create local users, services, scheduled tasks, or change host ACL.
Set-StrictMode -Version Latest

if (-not ('ViewtvSandboxRestrictedToken' -as [type])) {
    Add-Type -ReferencedAssemblies @('System.dll','System.Core.dll') -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Security.AccessControl;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
using System.Security.Principal;

public static class ViewtvSandboxRestrictedToken {
    [StructLayout(LayoutKind.Sequential)]
    private struct SID_AND_ATTRIBUTES {
        public IntPtr Sid;
        public UInt32 Attributes;
    }

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(
        IntPtr process, UInt32 access, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool CreateRestrictedToken(
        IntPtr token, UInt32 flags,
        UInt32 disableCount, [In] SID_AND_ATTRIBUTES[] disableSids,
        UInt32 deletePrivilegeCount, IntPtr deletePrivileges,
        UInt32 restrictCount, [In] SID_AND_ATTRIBUTES[] restrictedSids,
        out IntPtr restrictedToken);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool DuplicateTokenEx(
        IntPtr existingToken, UInt32 access, IntPtr attributes,
        Int32 impersonationLevel, Int32 tokenType,
        out IntPtr token);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode,
               SetLastError = true, EntryPoint = "CreateFileW")]
    private static extern SafeFileHandle OpenPipe(
        string name, uint access, uint share, IntPtr security,
        uint disposition, uint flags, IntPtr template);

    private static IntPtr SidPointer(SecurityIdentifier sid) {
        byte[] bytes = new byte[sid.BinaryLength];
        sid.GetBinaryForm(bytes, 0);
        IntPtr ptr = Marshal.AllocHGlobal(bytes.Length);
        Marshal.Copy(bytes, 0, ptr, bytes.Length);
        return ptr;
    }

    public static IntPtr Create() {
        IntPtr source = IntPtr.Zero, primary = IntPtr.Zero;
        IntPtr adminPtr = IntPtr.Zero, restrictedPtr = IntPtr.Zero;
        try {
            const uint TOKEN_DUPLICATE = 2;
            const uint TOKEN_QUERY = 8;
            if (!OpenProcessToken(GetCurrentProcess(),
                                  TOKEN_DUPLICATE | TOKEN_QUERY,
                                  out source))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            var admin = new SecurityIdentifier(
                WellKnownSidType.BuiltinAdministratorsSid, null);
            var restricted = new SecurityIdentifier(
                WellKnownSidType.RestrictedCodeSid, null);
            adminPtr = SidPointer(admin);
            restrictedPtr = SidPointer(restricted);
            SID_AND_ATTRIBUTES[] disabled = {
                new SID_AND_ATTRIBUTES { Sid = adminPtr, Attributes = 0 }
            };
            SID_AND_ATTRIBUTES[] limited = {
                new SID_AND_ATTRIBUTES { Sid = restrictedPtr, Attributes = 0 }
            };
            // DISABLE_MAX_PRIVILEGE and deny-only Administrators group:
            if (!CreateRestrictedToken(source, 1, 1, disabled,
                                       0, IntPtr.Zero, 1, limited,
                                       out primary))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            IntPtr impersonation;
            // SecurityImpersonation=2, TokenImpersonation=2
            if (!DuplicateTokenEx(primary, 0x02000000, IntPtr.Zero,
                                  2, 2, out impersonation))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            return impersonation;
        }
        finally {
            if (primary != IntPtr.Zero) CloseHandle(primary);
            if (source != IntPtr.Zero) CloseHandle(source);
            if (adminPtr != IntPtr.Zero) Marshal.FreeHGlobal(adminPtr);
            if (restrictedPtr != IntPtr.Zero) Marshal.FreeHGlobal(restrictedPtr);
        }
    }

    public static void DisposeToken(IntPtr handle) {
        if (handle != IntPtr.Zero) CloseHandle(handle);
    }

    public static bool StillAdministrator(IntPtr handle) {
        using (WindowsIdentity identity = new WindowsIdentity(handle)) {
            return new WindowsPrincipal(identity).IsInRole(
                WindowsBuiltInRole.Administrator);
        }
    }

    // Do NOT let the caller decide the SID or run arbitrary code.
    // Use fixed file operations only in the test sandbox.
    public static string Probe(IntPtr token, string operation,
                               string fullPath, string content) {
        WindowsImpersonationContext impersonation =
            WindowsIdentity.Impersonate(token);
        try {
            try {
                switch (operation) {
                    case "write":
                        File.WriteAllText(fullPath, content);
                        break;
                    case "read":
                        using (FileStream f = File.Open(
                               fullPath, FileMode.Open, FileAccess.Read,
                               FileShare.ReadWrite)) {
                            if (f.ReadByte() < 0)
                                return "empty";
                        }
                        break;
                    case "mkdir":
                        Directory.CreateDirectory(fullPath);
                        break;
                    case "fileacl":
                        var fileAcl = File.GetAccessControl(fullPath);
                        fileAcl.AddAccessRule(new FileSystemAccessRule(
                            new SecurityIdentifier(WellKnownSidType.RestrictedCodeSid,null),
                            FileSystemRights.FullControl, AccessControlType.Allow));
                        File.SetAccessControl(fullPath, fileAcl);
                        break;
                    case "diracl":
                        var folderAcl = Directory.GetAccessControl(fullPath);
                        folderAcl.AddAccessRule(new FileSystemAccessRule(
                            new SecurityIdentifier(WellKnownSidType.RestrictedCodeSid,null),
                            FileSystemRights.FullControl, AccessControlType.Allow));
                        Directory.SetAccessControl(fullPath, folderAcl);
                        break;
                    default:
                        throw new ArgumentException("Operation not supported");
                }
                return "allowed";
            }
            catch (UnauthorizedAccessException) {
                return "denied";
            }
            catch (IOException e) {
                // 0x80070005: E_ACCESSDENIED (some Win32 wrappers).
                if (e.HResult == unchecked((int)0x80070005))
                    return "denied";
                throw;
            }
        }
        finally {
            impersonation.Undo();
        }
    }

    // Open before seal: caller owns the handle and must close it.
    // This demonstrates why ACL changes do NOT revoke existing handles.
    public static FileStream OpenWriteHandle(IntPtr token, string fullPath) {
        WindowsImpersonationContext impersonation =
            WindowsIdentity.Impersonate(token);
        try {
            return new FileStream(fullPath, FileMode.Open, FileAccess.Write,
                FileShare.ReadWrite | FileShare.Delete);
        } finally {
            impersonation.Undo();
        }
    }

    public static SafeFileHandle OpenDirectoryHandle(IntPtr token, string fullPath) {
        WindowsImpersonationContext impersonation =
            WindowsIdentity.Impersonate(token);
        try {
            // FILE_LIST_DIRECTORY + share all; survives ACL sealing.
            SafeFileHandle handle = OpenPipe(fullPath, 1, 7, IntPtr.Zero, 3,
                                             0x02000000, IntPtr.Zero);
            if (handle.IsInvalid) {
                int code = Marshal.GetLastWin32Error();
                handle.Dispose();
                throw new Win32Exception(code);
            }
            return handle;
        } finally {
            impersonation.Undo();
        }
    }

    public static string ProbePipe(IntPtr token, string testPipeName) {
        if (!System.Text.RegularExpressions.Regex.IsMatch(testPipeName,
                @"\Aviewtv-test-pipe-[a-f0-9]{32}\z"))
            throw new ArgumentException("Invalid test pipe name.");
        WindowsImpersonationContext impersonation =
            WindowsIdentity.Impersonate(token);
        try {
            using (SafeFileHandle handle = OpenPipe(
                    @"\\.\pipe\" + testPipeName, 0xC0000000, 0,
                    IntPtr.Zero, 3, 0, IntPtr.Zero)) {
                if (!handle.IsInvalid) return "allowed";
                int code = Marshal.GetLastWin32Error();
                if (code == 5) return "denied";
                return "win32_" + code.ToString();
            }
        } finally {
            impersonation.Undo();
        }
    }
}
'@
}

function Assert-ViewtvRestrictedSandboxPath(
    [string]$Root, [string]$Path
) {
    $public=[IO.Path]::GetFullPath($env:PUBLIC).TrimEnd('\')
    $base=[IO.Path]::GetFullPath($Root).TrimEnd('\')
    if ($public -ine 'C:\Users\Public' -or
        [IO.Path]::GetDirectoryName($base) -ine $public -or
        [IO.Path]::GetFileName($base) -cnotmatch '^viewtv-win-sandbox-[0-9a-f]{32}$' -or
        -not [IO.Directory]::Exists($base) -or
        ([IO.DirectoryInfo]::new($base).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        [IO.File]::ReadAllText((Join-Path $base '.viewtv-win-sandbox-only')) -cne
          ('VIEWTV_WINDOWS_SANDBOX_ONLY_V1'+[char]10)) {
        throw 'No se admite acceso fuera de un sandbox GUID marcado.'
    }
    $canonical=[IO.Path]::GetFullPath($Path)
    if ($canonical -ieq $base) { return $canonical }
    if (-not $canonical.StartsWith($base+'\',[StringComparison]::OrdinalIgnoreCase)) {
        throw 'Ruta fuera del sandbox.'
    }
    $relative=$canonical.Substring($base.Length+1)
    foreach ($component in @($relative.Split('\'))) {
        if ($component.Length -eq 0 -or $component -in @('.','..')) {
            throw 'Ruta relativa incorrecta.'
        }
    }
    $current=$base
    $segments=$relative.Split('\')
    for ($i=0; $i -lt $segments.Count; $i++) {
        $current=Join-Path $current $segments[$i]
        if ([IO.File]::Exists($current) -or [IO.Directory]::Exists($current)) {
            $flags=[IO.File]::GetAttributes($current)
            if (($flags -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Un enlace de reanálisis impide la prueba.'
            }
        }
    }
    return $canonical
}

function Invoke-ViewtvRestrictedSandboxOperation(
    [IntPtr]$Token, [string]$Root,
    [ValidateSet('write','read','mkdir','fileacl','diracl')][string]$Operation,
    [string]$Path, [string]$Text = 'contenido ficticio'
) {
    $path=Assert-ViewtvRestrictedSandboxPath $Root $Path
    return [ViewtvSandboxRestrictedToken]::Probe(
        $Token,$Operation,$path,$Text)
}
