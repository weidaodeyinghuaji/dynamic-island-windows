import subprocess
from types import SimpleNamespace

import pytest

import plugins.music_control as music_control


def test_media_fallback_uses_script_next_to_plugin(monkeypatch, tmp_path, qapp):
    plugin_dir = tmp_path / "installed" / "plugins"
    plugin_dir.mkdir(parents=True)
    fallback_script = plugin_dir / "get_media.ps1"
    fallback_script.touch()
    monkeypatch.setattr(music_control, "__file__", str(plugin_dir / "music_control.py"))

    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(stdout="" if len(calls) == 1 else "Song|Artist|Playing")

    monkeypatch.setattr(music_control.subprocess, "run", fake_run)
    result = []
    fetcher = music_control.MediaInfoFetcher()
    fetcher.info_ready.connect(lambda title, artist: result.append((title, artist)))

    fetcher.run()

    assert len(calls) == 2
    assert calls[1][-1] == str(fallback_script)
    assert result == [("Song", "Artist")]


def test_media_fallback_missing_script_keeps_waiting(monkeypatch, tmp_path, qapp):
    monkeypatch.setattr(music_control, "__file__", str(tmp_path / "music_control.py"))
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(music_control.subprocess, "run", fake_run)
    result = []
    fetcher = music_control.MediaInfoFetcher()
    fetcher.info_ready.connect(lambda title, artist: result.append((title, artist)))

    fetcher.run()

    assert len(calls) == 1
    assert result == [("音乐", "等待播放...")]


def test_media_primary_result_does_not_run_fallback(monkeypatch, tmp_path, qapp):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "get_media.ps1").touch()
    monkeypatch.setattr(music_control, "__file__", str(plugin_dir / "music_control.py"))
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(stdout="Song|Artist|Playing")

    monkeypatch.setattr(music_control.subprocess, "run", fake_run)
    result = []
    fetcher = music_control.MediaInfoFetcher()
    fetcher.info_ready.connect(lambda title, artist: result.append((title, artist)))

    fetcher.run()

    assert len(calls) == 1
    assert result == [("Song", "Artist")]


@pytest.mark.parametrize("failure", ["timeout", "missing_executable"])
def test_media_primary_error_uses_fallback(monkeypatch, tmp_path, qapp, failure):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    fallback_script = plugin_dir / "get_media.ps1"
    fallback_script.touch()
    monkeypatch.setattr(music_control, "__file__", str(plugin_dir / "music_control.py"))
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        if len(calls) == 1:
            if failure == "timeout":
                raise subprocess.TimeoutExpired("powershell.exe", 3)
            raise OSError("PowerShell unavailable")
        return SimpleNamespace(stdout="Song|Artist|Playing")

    monkeypatch.setattr(music_control.subprocess, "run", fake_run)
    result = []
    fetcher = music_control.MediaInfoFetcher()
    fetcher.info_ready.connect(lambda title, artist: result.append((title, artist)))

    fetcher.run()

    assert len(calls) == 2
    assert calls[1][-1] == str(fallback_script)
    assert result == [("Song", "Artist")]


def test_media_fallback_error_keeps_waiting(monkeypatch, tmp_path, qapp):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "get_media.ps1").touch()
    monkeypatch.setattr(music_control, "__file__", str(plugin_dir / "music_control.py"))
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(stdout="" if len(calls) == 1 else "Error|unavailable|Stopped")

    monkeypatch.setattr(music_control.subprocess, "run", fake_run)
    result = []
    fetcher = music_control.MediaInfoFetcher()
    fetcher.info_ready.connect(lambda title, artist: result.append((title, artist)))

    fetcher.run()

    assert len(calls) == 2
    assert result == [("音乐", "等待播放...")]
