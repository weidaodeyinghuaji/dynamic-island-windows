param()
[System.Reflection.Assembly]::LoadWithPartialName("System.Runtime.WindowsRuntime") | Out-Null
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType = WindowsRuntime] | Out-Null
$manager = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync().GetAwaiter().GetResult()
$session = $manager.GetCurrentSession()
if ($session) {
    $props = $session.TryGetMediaPropertiesAsync().GetAwaiter().GetResult()
    Write-Output ($props.Title + "|" + $props.Artist)
}
