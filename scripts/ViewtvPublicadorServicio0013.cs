// Adaptador de Windows Service Control Manager. No publica ni accede a SQLite.
// El proceso PowerShell Windows tiene las validaciones NTFS y la cola 0013.
// Se compila con csc.exe del .NET Framework 4.x: no requiere librerías externas.
using System;
using System.Diagnostics;
using System.IO;
using System.ServiceProcess;
using System.Threading;

public sealed class ViewtvPublicadorServicio0013 : ServiceBase
{
    private Process child;
    private bool stopping;
    private readonly object gate = new object();

    public ViewtvPublicadorServicio0013()
    {
        ServiceName = "ViewtvPublicador0013";
        CanStop = true;
        AutoLog = true;
    }

    protected override void OnStart(string[] args)
    {
        string script = @"C:\VIEWTV\publicador\bin\viewtv_windows_publicador_0013.ps1";
        if (!File.Exists(script))
            throw new FileNotFoundException("Publicador Windows no instalado.");
        var start = new ProcessStartInfo();
        start.FileName = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.System),
            @"WindowsPowerShell\v1.0\powershell.exe");
        start.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass " +
                          "-File \"" + script + "\" -Mode Loop";
        start.WorkingDirectory = @"C:\VIEWTV\publicador\bin";
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        lock (gate)
        {
            stopping = false;
            child = Process.Start(start);
            if (child == null)
                throw new InvalidOperationException("No se pudo lanzar el publicador.");
        }
        var watchdog = new Thread(() => {
            Process process;
            lock (gate) { process = child; }
            if (process == null) return;
            process.WaitForExit();
            lock (gate) {
                if (!stopping)
                    Environment.Exit(1); // SCM recovery, sin un segundo publicador paralelo.
            }
        });
        watchdog.IsBackground = true;
        watchdog.Start();
    }

    protected override void OnStop()
    {
        lock (gate)
        {
            stopping = true;
            if (child != null && !child.HasExited)
            {
                child.Kill();
                child.WaitForExit(5000);
            }
        }
    }

    public static void Main()
    {
        ServiceBase.Run(new ViewtvPublicadorServicio0013());
    }
}
