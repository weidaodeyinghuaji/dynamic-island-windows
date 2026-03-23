param()

# 加载 Windows Runtime 支持
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType = WindowsRuntime] | Out-Null

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    
    $code = @"
using System;
using System.Threading.Tasks;
using Windows.Media.Control;

namespace MediaHelper
{
    public class MediaInfoHelper
    {
        public static string GetMediaInfo()
        {
            try
            {
                var manager = GlobalSystemMediaTransportControlsSessionManager.RequestAsync().GetAwaiter().GetResult();
                var session = manager.GetCurrentSession();
                if (session != null)
                {
                    var props = session.TryGetMediaPropertiesAsync().GetAwaiter().GetResult();
                    var playbackInfo = session.GetPlaybackInfo();
                    var status = playbackInfo.PlaybackStatus.ToString();
                    
                    string title = props.Title;
                    if (string.IsNullOrEmpty(title)) { title = "音乐"; }
                    
                    return title + "|" + props.Artist + "|" + status;
                }
                return "||Stopped";
            }
            catch (Exception ex)
            {
                return "Error|" + ex.Message + "|Stopped";
            }
        }
    }
}
"@
    
    Add-Type -TypeDefinition $code -Language CSharp -CompilerParameters @(
        "-reference:System.Runtime.WindowsRuntime.dll",
        "-reference:Windows.Media.dll"
    ) -ErrorAction Ignore
    
    $result = [MediaHelper.MediaInfoHelper]::GetMediaInfo()
    Write-Output $result

} catch {
    Write-Output "||Stopped"
}