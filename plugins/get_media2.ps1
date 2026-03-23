param()
Add-Type -TypeDefinition @"
using System;
using System.Threading.Tasks;
using Windows.Media.Control;

public class MediaHelper {
    public static string GetMediaInfo() {
        var task = GlobalSystemMediaTransportControlsSessionManager.RequestAsync().AsTask();
        task.Wait();
        var manager = task.Result;
        var session = manager.GetCurrentSession();
        if (session == null) return "";
        var propsTask = session.TryGetMediaPropertiesAsync().AsTask();
        propsTask.Wait();
        var props = propsTask.Result;
        return props.Title + "|" + props.Artist;
    }
}
"@ -ReferencedAssemblies "System.Runtime.WindowsRuntime", "Windows"
[MediaHelper]::GetMediaInfo()
