# VIEWTV — NTFS file identity preflight. TEST SANDBOX ONLY.
# Native IDs are an additional fail-closed check; no atomic NTFS+SQLite guarantee.
Set-StrictMode -Version Latest

if (-not ('ViewtvSandboxNtfsIdentity' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class ViewtvSandboxNtfsIdentity {
    [StructLayout(LayoutKind.Sequential)]
    public struct FILETIME { public uint Low; public uint High; }
    [StructLayout(LayoutKind.Sequential)]
    public struct BY_HANDLE_FILE_INFORMATION {
        public uint FileAttributes;
        public FILETIME CreationTime;
        public FILETIME LastAccessTime;
        public FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true, EntryPoint="CreateFileW")]
    private static extern SafeFileHandle Open(
        string path, uint access, uint share, IntPtr security,
        uint mode, uint flags, IntPtr template
    );
    [DllImport("kernel32.dll", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle handle, out BY_HANDLE_FILE_INFORMATION info
    );
    public static string Fingerprint(string path, bool file) {
        // FILE_READ_ATTRIBUTES; share all so a preflight does not monopolize
        // the object; OPEN_REPARSE_POINT forbids following symlink targets.
        using (var handle = Open(path, 0x80, 7, IntPtr.Zero, 3,
                                 0x02000000 | 0x00200000, IntPtr.Zero)) {
            if (handle.IsInvalid)
                throw new Win32Exception(Marshal.GetLastWin32Error());
            BY_HANDLE_FILE_INFORMATION info;
            if (!GetFileInformationByHandle(handle, out info))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            const uint REPARSE_POINT = 0x400;
            const uint DIRECTORY = 0x10;
            if ((info.FileAttributes & REPARSE_POINT) != 0)
                throw new InvalidOperationException("Entrada NTFS redirigida.");
            if (file && ((info.FileAttributes & DIRECTORY) != 0 ||
                         info.NumberOfLinks != 1))
                throw new InvalidOperationException("Archivo inseguro (enlace o carpeta).");
            if (!file && (info.FileAttributes & DIRECTORY) == 0)
                throw new InvalidOperationException("La carpeta de staging cambió.");
            return info.VolumeSerialNumber.ToString("X8") + ":" +
                   info.FileIndexHigh.ToString("X8") + ":" +
                   info.FileIndexLow.ToString("X8");
        }
    }
}
'@
}

function Get-ViewtvTestFolderFingerprint([string]$Root, [string]$FolderName) {
    # The caller must already have validated the GUID root and marker.
    if ([string]::IsNullOrWhiteSpace($FolderName) -or
        $FolderName -in @('.','..') -or
        $FolderName -match '[<>:"/\\|?*\x00-\x1f]' -or
        $FolderName.EndsWith('.') -or
        $FolderName.Trim() -cne $FolderName) {
        throw 'Nombre de carpeta de prueba incorrecto.'
    }
    $folder = Join-Path $Root $FolderName
    $stamp = [ordered]@{
        carpeta = [ViewtvSandboxNtfsIdentity]::Fingerprint($folder,$false)
    }
    $files = @([IO.Directory]::GetFileSystemEntries($folder))
    if ($files.Count -lt 1 -or $files.Count -gt 20) {
        throw 'Conjunto inesperado de archivos en staging.'
    }
    foreach ($file in @($files | Sort-Object)) {
        $name = [IO.Path]::GetFileName($file)
        $stamp[$name] = [ViewtvSandboxNtfsIdentity]::Fingerprint($file,$true)
    }
    return ($stamp | ConvertTo-Json -Compress)
}
function Get-ViewtvTestStageFingerprint([string]$Root, [string]$StageName) {
    if ($StageName -cnotmatch '^\.viewtv-stage-[1-9][0-9]{0,9}$') {
        throw 'Identidad de staging incorrecta.'
    }
    return Get-ViewtvTestFolderFingerprint $Root $StageName
}
