# VIEWTV: native Win32 FIRST_PIPE_INSTANCE, SANDBOX ONLY.
# Requires an already inspected PipeSecurity with a protected DACL.
Set-StrictMode -Version Latest

if (-not ('ViewtvNativeFirstPipeInstance' -as [type])) {
    Add-Type -ReferencedAssemblies @('System.Core.dll','System.dll') -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class ViewtvNativeFirstPipeInstance {
    [StructLayout(LayoutKind.Sequential)]
    private struct SECURITY_ATTRIBUTES {
        public int nLength;
        public IntPtr lpSecurityDescriptor;
        public int bInheritHandle;
    }

    [DllImport("kernel32.dll", EntryPoint="CreateNamedPipeW",
        CharSet=CharSet.Unicode, SetLastError=true, ExactSpelling=true)]
    private static extern SafePipeHandle CreateNamedPipe(
        string lpName, uint dwOpenMode, uint dwPipeMode,
        uint nMaxInstances, uint nOutBufferSize, uint nInBufferSize,
        uint nDefaultTimeOut, ref SECURITY_ATTRIBUTES lpSecurityAttributes
    );

    public static SafePipeHandle Open(string pipeName, byte[] daclBytes) {
        if (pipeName == null ||
            !System.Text.RegularExpressions.Regex.IsMatch(
                pipeName, @"\Aviewtv-test-pipe-[a-f0-9]{32}\z",
                System.Text.RegularExpressions.RegexOptions.CultureInvariant)) {
            throw new ArgumentException("Sandbox pipe name required.");
        }
        if (daclBytes == null || daclBytes.Length < 32 ||
            daclBytes.Length > 8192) {
            throw new ArgumentException("Sandbox security descriptor required.");
        }

        IntPtr descriptor = Marshal.AllocHGlobal(daclBytes.Length);
        try {
            Marshal.Copy(daclBytes, 0, descriptor, daclBytes.Length);
            SECURITY_ATTRIBUTES sa = new SECURITY_ATTRIBUTES();
            sa.nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES));
            sa.lpSecurityDescriptor = descriptor;
            sa.bInheritHandle = 0;
            // PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE |
            // FILE_FLAG_OVERLAPPED. Fails if a pipe of this name exists.
            const uint openMode = 0x00000003 | 0x00080000 | 0x40000000;
            const uint byteMode = 0x00000000;
            SafePipeHandle handle = CreateNamedPipe(
                @"\\.\pipe\" + pipeName,
                openMode, byteMode, 1, 4096, 4096, 0, ref sa);
            if (handle == null || handle.IsInvalid) {
                int code = Marshal.GetLastWin32Error();
                if (handle != null) handle.Dispose();
                throw new Win32Exception(code, "Native first pipe instance failed.");
            }
            return handle;
        } finally {
            Marshal.FreeHGlobal(descriptor);
        }
    }
}
'@
}

function New-ViewtvBrokerNativeFirstPipe(
    [string]$PipeName, [IO.Pipes.PipeSecurity]$Security
) {
    if ($PipeName -cnotmatch '^viewtv-test-pipe-[a-f0-9]{32}$') {
        throw 'Nombre de tubería fuera del ensayo.'
    }
    if ($null -eq $Security -or -not $Security.AreAccessRulesProtected) {
        throw 'Se requiere DACL protegida.'
    }
    $descriptor = $Security.GetSecurityDescriptorBinaryForm()
    $handle = [ViewtvNativeFirstPipeInstance]::Open($PipeName,$descriptor)
    try {
        # Public .NET Framework constructor wraps the native OVERLAPPED
        # handle, without constructing a second named pipe instance.
        $stream = [IO.Pipes.NamedPipeServerStream]::new(
            [IO.Pipes.PipeDirection]::InOut, $true, $false, $handle)
        return $stream
    } catch {
        $handle.Dispose()
        throw
    }
}
