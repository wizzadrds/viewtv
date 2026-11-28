// VIEWTV 0052 - inert Windows health-only staged broker.
// NO qbittorrent references, media paths, START/STOP, unlink or config writes.
// Requires Windows Service SID NT SERVICE\VIEWTV-Broker-0052 and LocalService.
using System;
using System.IO;
using System.IO.Pipes;
using System.Security.AccessControl;
using System.Security.Principal;
using System.ServiceProcess;
using System.Text;
using System.Threading;

internal sealed class ViewtvBroker0052 : ServiceBase
{
    private const string Name0052 = "VIEWTV-Broker-0052";
    private const string Pipe0052 = "viewtv-0052-inert-health";
    private const string StatePath = @"C:\ProgramData\VIEWTV-Broker-0052\data\state.txt";
    private const string LocalServiceSid = "S-1-5-19";
    private Thread loop;
    private volatile bool stopping;
    private volatile bool healthy;
    private NamedPipeServerStream server;

    private static SecurityIdentifier BrokerSid()
    {
        return (SecurityIdentifier)new NTAccount(@"NT SERVICE\VIEWTV-Broker-0052")
            .Translate(typeof(SecurityIdentifier));
    }
    private static bool HasEnabledGroup(WindowsIdentity identity, SecurityIdentifier sid)
    {
        if (identity == null || identity.Groups == null) return false;
        foreach (IdentityReference item in identity.Groups)
            if (item.Value == sid.Value) return true;
        return false;
    }
    private static bool IsBrokerToken()
    {
        using (WindowsIdentity id = WindowsIdentity.GetCurrent())
            return id.User != null && id.User.Value == LocalServiceSid
                && HasEnabledGroup(id, BrokerSid());
    }
    private static PipeSecurity RestrictedPipeAcl()
    {
        PipeSecurity acl = new PipeSecurity();
        acl.SetAccessRuleProtection(true, false);
        acl.AddAccessRule(new PipeAccessRule(
            BrokerSid(), PipeAccessRights.FullControl, AccessControlType.Allow));
        return acl;
    }
    private static NamedPipeServerStream MakeServer()
    {
        return new NamedPipeServerStream(Pipe0052, PipeDirection.InOut, 1,
            PipeTransmissionMode.Byte, PipeOptions.Asynchronous,
            512, 512, RestrictedPipeAcl());
    }
    public ViewtvBroker0052()
    {
        ServiceName = Name0052;
        CanStop = true;
        CanPauseAndContinue = false;
        AutoLog = false;
    }
    protected override void OnStart(string[] args)
    {
        if (!IsBrokerToken())
            throw new InvalidOperationException("SID de servicio no verificado.");
        stopping = false;
        healthy = false;
        loop = new Thread(ServerLoop);
        loop.IsBackground = true;
        loop.Start();
        ThreadPool.QueueUserWorkItem(_ => SelfTest());
    }
    private void RecordHealthy()
    {
        if (healthy) return;
        // Only categorical results, never SID strings, secrets or hash values.
        File.WriteAllText(StatePath,
            "IDENTIDAD_LOCALSERVICE=PASS\n"+
            "SID_SERVICIO_EN_TOKEN=PASS\n"+
            "PIPE_SOLO_SID_SERVICIO=PASS\n"+
            "SELFTEST_HEALTH_EN_SERVICIO=PASS\n"+
            "FUNCIONES_MEDIA_O_QBIT=NO\n"+
            "CAMBIOS_CONFIG_PRODUCCION=0\n", Encoding.ASCII);
        healthy = true;
    }
    private void ServerLoop()
    {
        while (!stopping)
        {
            NamedPipeServerStream pipe = null;
            try
            {
                pipe = MakeServer();
                server = pipe;
                pipe.WaitForConnection();
                bool validPeer = false;
                pipe.RunAsClient(delegate() {
                    using (WindowsIdentity peer = WindowsIdentity.GetCurrent(true))
                        validPeer = peer.User != null
                            && peer.User.Value == LocalServiceSid
                            && HasEnabledGroup(peer, BrokerSid());
                });
                // The service has no actions beyond answering an exact health check.
                // Only the service SID can connect; no external callers.
                using (StreamReader input = new StreamReader(pipe, Encoding.ASCII, false, 64, true))
                using (StreamWriter output = new StreamWriter(pipe, Encoding.ASCII, 64, true))
                {
                    string command = input.ReadLine();
                    output.NewLine = "\n";
                    if (validPeer && command == "HEALTH")
                    {
                        output.WriteLine("VIEWTV_0052_ONLY_HEALTH");
                        output.Flush();
                        RecordHealthy();
                    }
                    else
                    {
                        output.WriteLine("DENIED");
                        output.Flush();
                    }
                }
            }
            catch (Exception) { /* No change, no re-execute, no retry of an effect */ }
            finally
            {
                if (pipe != null) pipe.Dispose();
                server = null;
            }
        }
    }
    private void SelfTest()
    {
        for (int attempt = 0; attempt < 10 && !healthy && !stopping; attempt++)
        {
            try
            {
                using (NamedPipeClientStream client = new NamedPipeClientStream(
                    ".", Pipe0052, PipeDirection.InOut, PipeOptions.None,
                    TokenImpersonationLevel.Impersonation))
                {
                    client.Connect(2000);
                    using (StreamWriter output = new StreamWriter(client, Encoding.ASCII, 64, true))
                    using (StreamReader input = new StreamReader(client, Encoding.ASCII, false, 64, true))
                    {
                        output.NewLine = "\n";
                        output.WriteLine("HEALTH");
                        output.Flush();
                        if (input.ReadLine() == "VIEWTV_0052_ONLY_HEALTH")
                            return;
                    }
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            catch (System.TimeoutException) { }
            Thread.Sleep(150);
        }
    }
    protected override void OnStop()
    {
        stopping = true;
        if (server != null) server.Dispose();
        if (loop != null) loop.Join(2000);
    }
    private static void Main()
    {
        ServiceBase.Run(new ViewtvBroker0052());
    }
}
