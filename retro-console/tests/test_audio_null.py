import pytest

from rwt_rconsole import (
    AudioChannels,
    AudioConfig,
    AudioPlaybackState,
    AudioSampleFormat,
    NullAudio,
    as_float32,
    clear_audio_backend,
    register_audio_backend,
    suggested_audio_config,
)


def test_validate_rejects_invalid():
    AudioConfig(sample_rate=44100, channels=AudioChannels.STEREO, format=AudioSampleFormat.FLOAT32)
    with pytest.raises(ValueError):
        AudioConfig(sample_rate=0)


def test_as_float32_view():
    raw = bytearray(4 * 4)
    floats = as_float32(memoryview(raw))
    assert len(floats) == 4
    floats[0] = 0.5
    floats[1] = -1.0
    again = as_float32(memoryview(raw))
    assert again[0] == pytest.approx(0.5)
    assert again[1] == pytest.approx(-1.0)


def test_null_audio_play_pause_stop():
    config = AudioConfig(
        sample_rate=44100,
        channels=AudioChannels.STEREO,
        format=AudioSampleFormat.FLOAT32,
        reverb=50,
    )

    def callback(dst: memoryview) -> None:
        floats = as_float32(dst)
        for i in range(len(floats)):
            floats[i] = 0.25

    with NullAudio(config, callback) as audio:
        assert audio.state is AudioPlaybackState.STOPPED
        assert audio.reverb == 50

        buf = bytearray(4 * 4)
        audio.simulate_render(buf)
        assert as_float32(memoryview(buf))[0] == 0.0

        audio.play()
        assert audio.state is AudioPlaybackState.PLAYING
        audio.simulate_render(buf)
        assert as_float32(memoryview(buf))[0] == pytest.approx(0.25)

        audio.pause()
        assert audio.state is AudioPlaybackState.PAUSED
        audio.simulate_render(buf)
        assert as_float32(memoryview(buf))[0] == 0.0

        audio.stop()
        assert audio.state is AudioPlaybackState.STOPPED


def test_callback_exception_stops_and_stores_error():
    config = AudioConfig(channels=AudioChannels.MONO, format=AudioSampleFormat.INT16)

    def callback(_dst: memoryview) -> None:
        raise RuntimeError("Synthesizer error!")

    with NullAudio(config, callback) as audio:
        audio.play()
        assert audio.last_error is None
        buf = bytearray(16)
        audio.simulate_render(buf)
        assert audio.state is AudioPlaybackState.STOPPED
        assert audio.last_error is not None
        assert "Synthesizer error!" in str(audio.last_error)


def test_registry_suggested_config():
    clear_audio_backend()

    class Dummy:
        def suggested_config(self):
            return AudioConfig(sample_rate=48000)

        def create(self, config, callback):
            return NullAudio(config, callback)

    register_audio_backend(Dummy())
    assert suggested_audio_config().sample_rate == 48000
    clear_audio_backend()
    assert suggested_audio_config().sample_rate == 44100
