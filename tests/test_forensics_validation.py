"""
test_forensics_validation.py — Empirical Validation of Audio & Media Forensics
=============================================================================
Validates TruthLens AI's existing audio stream heuristics and forensic analysis
against labeled synthetic/tampered media profiles vs organic/genuine media profiles.

Measures:
  - True Positive Rate (TPR / Sensitivity) on synthetic/tampered audio
  - True Negative Rate (TNR / Specificity) on genuine organic audio
  - False Positive Rate (FPR)
  - Detection thresholds (sample rates 22050/24000 Hz, silence burst counts, bitrates)
"""

import os
import sys
import unittest
from typing import Dict, List, Any

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.services.forensics import analyze_deepfake_heuristics


class TestForensicsValidation(unittest.TestCase):
    """Empirically evaluates existing forensic heuristics on labeled media cases."""

    def setUp(self):
        # Ground truth test media profiles
        # Synthetic / Tampered media:
        self.synthetic_profiles = [
            {
                "id": "syn-01",
                "label": "synthetic",
                "description": "Neural TTS 22.05kHz export with robotic artifacts",
                "transcript": "Hello viewers today I announce a secret investment fund giving 10x returns guaranteed.",
                "url": "https://example.com/video1.mp4",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 22050,
                    "channels": 1,
                    "codec_name": "aac",
                    "bit_rate_kbps": 28.0,
                    "duration_seconds": 15.2,
                    "silence_burst_count": 8,
                    "technical_anomaly_score": 0.70,
                    "technical_flags": [
                        "Unusual sample rate (22050 Hz) characteristic of neural TTS / voice models",
                        "Very low audio bitrate (28.0 kbps) — possible artifact suppression",
                        "Multiple abrupt silence gaps detected (8 cuts) — possible splice/sentence grafting"
                    ],
                }
            },
            {
                "id": "syn-02",
                "label": "synthetic",
                "description": "Voice clone 24kHz with spliced phrase repetition",
                "transcript": "This is completely real. This is completely real. This is completely real. Deposit money now.",
                "url": "https://example.com/video2.mp4",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 24000,
                    "channels": 1,
                    "codec_name": "mp3",
                    "bit_rate_kbps": 30.0,
                    "duration_seconds": 10.0,
                    "silence_burst_count": 7,
                    "technical_anomaly_score": 0.55,
                    "technical_flags": [
                        "Unusual sample rate (24000 Hz) characteristic of neural TTS / voice models",
                        "Multiple abrupt silence gaps detected (7 cuts) — possible splice/sentence grafting"
                    ],
                }
            },
            {
                "id": "syn-03",
                "label": "synthetic",
                "description": "Audio with self-referential manipulation clues and low bitrate",
                "transcript": "Notice how voices were changed and the recording was manipulated to sound like him.",
                "url": "https://example.com/video3.mp4",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 44100,
                    "channels": 1,
                    "codec_name": "aac",
                    "bit_rate_kbps": 24.0,
                    "duration_seconds": 22.0,
                    "silence_burst_count": 10,
                    "technical_anomaly_score": 0.40,
                    "technical_flags": [
                        "Very low audio bitrate (24.0 kbps) — possible artifact suppression",
                        "Multiple abrupt silence gaps detected (10 cuts) — possible splice/sentence grafting"
                    ],
                }
            },
            {
                "id": "syn-04",
                "label": "synthetic",
                "description": "TTS voice with lip sync off and unnatural speech cues",
                "transcript": "The audio doesn't match his face and lip sync is off throughout the entire address.",
                "url": "https://example.com/video4.mp4",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 22050,
                    "channels": 1,
                    "codec_name": "opus",
                    "bit_rate_kbps": 64.0,
                    "duration_seconds": 18.5,
                    "silence_burst_count": 6,
                    "technical_anomaly_score": 0.55,
                    "technical_flags": [
                        "Unusual sample rate (22050 Hz) characteristic of neural TTS / voice models",
                        "Multiple abrupt silence gaps detected (6 cuts) — possible splice/sentence grafting"
                    ],
                }
            },
        ]

        # Genuine / Organic media:
        self.organic_profiles = [
            {
                "id": "org-01",
                "label": "organic",
                "description": "Standard studio broadcast recording 48kHz stereo 192kbps",
                "transcript": "The central bank monetary policy committee met today in Washington to discuss interest rate decisions.",
                "url": "https://example.com/news_broadcast.mp4",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 48000,
                    "channels": 2,
                    "codec_name": "aac",
                    "bit_rate_kbps": 192.0,
                    "duration_seconds": 45.0,
                    "silence_burst_count": 1,
                    "technical_anomaly_score": 0.0,
                    "technical_flags": [],
                }
            },
            {
                "id": "org-02",
                "label": "organic",
                "description": "Standard podcast episode 44.1kHz stereo 128kbps",
                "transcript": "Welcome back to our weekly science podcast where we explore recent astrophysics discoveries and exoplanets.",
                "url": "https://example.com/podcast.mp3",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 44100,
                    "channels": 2,
                    "codec_name": "mp3",
                    "bit_rate_kbps": 128.0,
                    "duration_seconds": 60.0,
                    "silence_burst_count": 2,
                    "technical_anomaly_score": 0.0,
                    "technical_flags": [],
                }
            },
            {
                "id": "org-03",
                "label": "organic",
                "description": "Casual phone voice recording 44.1kHz mono 96kbps with normal pauses",
                "transcript": "Hey Sarah, I'm heading over to the grocery store now, let me know if you need any apples or bread.",
                "url": "https://example.com/voice_memo.m4a",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 44100,
                    "channels": 1,
                    "codec_name": "aac",
                    "bit_rate_kbps": 96.0,
                    "duration_seconds": 8.0,
                    "silence_burst_count": 1,
                    "technical_anomaly_score": 0.0,
                    "technical_flags": [],
                }
            },
            {
                "id": "org-04",
                "label": "organic",
                "description": "Documentary narration with musical background 48kHz stereo 256kbps",
                "transcript": "In the remote regions of the Arctic tundra, temperatures drop below freezing for more than six months every year.",
                "url": "https://example.com/documentary.mp4",
                "technical_audio": {
                    "audio_stream_available": True,
                    "sample_rate": 48000,
                    "channels": 2,
                    "codec_name": "aac",
                    "bit_rate_kbps": 256.0,
                    "duration_seconds": 72.0,
                    "silence_burst_count": 0,
                    "technical_anomaly_score": 0.0,
                    "technical_flags": [],
                }
            },
        ]

    def test_forensics_accuracy_metrics(self):
        """Measures TPR, TNR, FPR, and veto precision on labeled media."""
        tp = 0
        fn = 0
        fp = 0
        tn = 0

        print("\n--- Forensics Empirical Validation on Labeled Media ---")
        for item in self.synthetic_profiles:
            res = analyze_deepfake_heuristics(
                transcript=item["transcript"],
                video_url=item["url"],
                technical_audio=item["technical_audio"]
            )
            is_detected = res["is_synthetic"]
            prob = max(res["deepfake_probability"], res["voice_clone_probability"])
            print(f"[SYNTHETIC] {item['id']}: prob={prob:.2f}, detected={is_detected} | {item['description']}")
            if is_detected:
                tp += 1
            else:
                fn += 1

        for item in self.organic_profiles:
            res = analyze_deepfake_heuristics(
                transcript=item["transcript"],
                video_url=item["url"],
                technical_audio=item["technical_audio"]
            )
            is_detected = res["is_synthetic"]
            prob = max(res["deepfake_probability"], res["voice_clone_probability"])
            print(f"[ORGANIC]   {item['id']}: prob={prob:.2f}, detected={is_detected} | {item['description']}")
            if is_detected:
                fp += 1
            else:
                tn += 1

        tpr = tp / (tp + fn) if (tp + fn) else 0.0
        tnr = tn / (tn + fp) if (tn + fp) else 0.0
        fpr = fp / (fp + tn) if (fp + tn) else 0.0

        print(f"\n--- Forensics Metrics Summary ---")
        print(f"True Positive Rate (Sensitivity) : {tpr * 100:.1f}% ({tp}/{tp+fn})")
        print(f"True Negative Rate (Specificity) : {tnr * 100:.1f}% ({tn}/{tn+fp})")
        print(f"False Positive Rate              : {fpr * 100:.1f}% ({fp}/{fp+tn})")

        # Validation assertions
        self.assertGreaterEqual(tpr, 0.75, "Forensics should detect at least 75% of synthetic profiles")
        self.assertLessEqual(fpr, 0.10, "Forensics false positive rate on organic media must be <= 10%")
        self.assertEqual(fp, 0, "Organic media should not trigger synthetic media veto")


if __name__ == "__main__":
    unittest.main()
