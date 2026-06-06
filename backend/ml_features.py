import os
import tempfile

import librosa
import numpy as np
from tinytag import TinyTag

MFCC_COUNT = 13
CHROMA_COUNT = 12

FEATURE_NAMES = [
    "duration_seconds",
    "tempo",
    "rms_mean",
    "rms_std",
    "zero_crossing_rate_mean",
    "spectral_centroid_mean",
    "spectral_centroid_std",
    "spectral_bandwidth_mean",
    "spectral_rolloff_mean",
    "spectral_contrast_mean",
]
FEATURE_NAMES += [f"mfcc_{i}_mean" for i in range(1, MFCC_COUNT + 1)]
FEATURE_NAMES += [f"chroma_{i}_mean" for i in range(1, CHROMA_COUNT + 1)]


def _float(value, default=0.0):
    if value is None:
        return default
    value = float(np.asarray(value).reshape(-1)[0])
    if np.isnan(value) or np.isinf(value):
        return default
    return value


def _mean(values):
    return _float(np.nanmean(values))


def _std(values):
    return _float(np.nanstd(values))


def _safe_feature(callable_value, fallback_shape=None):
    try:
        return callable_value()
    except Exception:
        if fallback_shape is None:
            return np.array([0.0])
        return np.zeros(fallback_shape)


def extract_audio_features(file_bytes: bytes, filename: str = "uploaded-audio"):
    suffix = os.path.splitext(filename or "uploaded-audio")[1] or ".mp3"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=22050, mono=True)
        if y.size == 0:
            raise ValueError("Audio file is empty after decoding")

        tag = TinyTag.get(tmp_path)

        duration = _float(librosa.get_duration(y=y, sr=sr))
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms = librosa.feature.rms(y=y)
        zcr = librosa.feature.zero_crossing_rate(y)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        contrast = _safe_feature(
            lambda: librosa.feature.spectral_contrast(y=y, sr=sr),
            fallback_shape=(7, max(1, rms.shape[1])),
        )
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=MFCC_COUNT)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)

        features = {
            "duration_seconds": duration,
            "tempo": _float(tempo),
            "rms_mean": _mean(rms),
            "rms_std": _std(rms),
            "zero_crossing_rate_mean": _mean(zcr),
            "spectral_centroid_mean": _mean(centroid),
            "spectral_centroid_std": _std(centroid),
            "spectral_bandwidth_mean": _mean(bandwidth),
            "spectral_rolloff_mean": _mean(rolloff),
            "spectral_contrast_mean": _mean(contrast),
        }

        for index, value in enumerate(np.nanmean(mfcc, axis=1), start=1):
            features[f"mfcc_{index}_mean"] = _float(value)

        for index, value in enumerate(np.nanmean(chroma, axis=1), start=1):
            features[f"chroma_{index}_mean"] = _float(value)

        vector = [_float(features.get(name)) for name in FEATURE_NAMES]
        metadata = {
            "audio_title": tag.title,
            "audio_artist": tag.artist,
            "audio_album": tag.album,
            "audio_bitrate": tag.bitrate,
            "audio_samplerate": tag.samplerate,
            "audio_channels": tag.channels,
            "audio_genre": tag.genre,
            "audio_year": tag.year,
        }

        return features, vector, metadata
    finally:
        os.unlink(tmp_path)
