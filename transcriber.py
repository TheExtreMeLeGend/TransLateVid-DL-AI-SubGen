import importlib
import json
import csv
import torch
import logging
from typing import Dict, Optional

# === Patch robust pour hook_attention_weights ===
ts_transcribe = importlib.import_module("whisper_timestamped.transcribe")

# Hook sécurisé : ignore outs[2] == None
def _safe_hook_attention_weights(layer, ins, outs, index):
    if len(outs) < 3 or outs[2] is None:
        return
    x, sim, w = outs
    if w.shape[-2] <= 1:
        return
    return _orig_hook(layer, ins, outs, index)

# Recherche dynamique et remplacement
_orig_hook = None
for name in dir(ts_transcribe):
    if name.endswith("hook_attention_weights"):
        _orig_hook = getattr(ts_transcribe, name)
        setattr(ts_transcribe, name, _safe_hook_attention_weights)
        break

if _orig_hook is None:
    logging.getLogger(__name__).warning(
        "hook_attention_weights introuvable — patch non appliqué"
    )
# === Fin du patch ===

import whisper_timestamped as whisper
from utils import progress_queue, config

# Afficher les logs Whisper pour voir le verbose
logging.basicConfig(level=logging.INFO)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("whisper_timestamped").setLevel(logging.INFO)


def _fmt_time(sec: float) -> str:
    ms = int((sec - int(sec)) * 1000)
    total = int(sec)
    s = total % 60
    m = (total // 60) % 60
    h = total // 3600
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _write_all_outputs(result: Dict, base: str) -> None:
    try:
        with open(f"{base}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        with open(f"{base}.srt", "w", encoding="utf-8") as srt:
            for i, seg in enumerate(result.get("segments", []), start=1):
                s, e = _fmt_time(seg["start"]), _fmt_time(seg["end"])
                txt = seg.get("text", "").strip()
                srt.write(f"{i}\n{s} --> {e}\n{txt}\n\n")
        with open(f"{base}.vtt", "w", encoding="utf-8") as vtt:
            vtt.write("WEBVTT\n\n")
            for seg in result.get("segments", []):
                s = _fmt_time(seg["start"]).replace(",", ".")
                e = _fmt_time(seg["end"]).replace(",", ".")
                txt = seg.get("text", "").strip()
                vtt.write(f"{s} --> {e}\n{txt}\n\n")
        for sep, ext in [(",", "csv"), ("\t", "tsv")]:
            with open(f"{base}.{ext}", "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=sep)
                w.writerow(["start", "end", "text"])
                for seg in result.get("segments", []):
                    w.writerow([_fmt_time(seg["start"]), _fmt_time(seg["end"]), seg.get("text","").strip()])
    except Exception as e:
        logging.error(f"Erreur lors de l'écriture des fichiers: {e}")
        raise


def run_transcription(
    audio_path: str,
    base_name: str,
    model_name: Optional[str] = None,
    accurate: bool = False,
    vad_method: str = "silero:v3.1",
    language: Optional[str] = None,
    **kwargs
) -> Dict:
    defaults = {
        "language": language,
        "task": "transcribe",
        "vad": vad_method,
        "compute_word_confidence": True,
        "include_punctuation_in_confidence": True,
        "detect_disfluencies": True,
        "refine_whisper_precision": 0.1,
        "min_word_duration": 0.02,
        "trust_whisper_timestamps": False,
        "compression_ratio_threshold": 1.5,
        "logprob_threshold": -0.5,
        "no_speech_threshold": 0.5,
        "condition_on_previous_text": True,
        "suppress_tokens": "-1",
        "# Afficher live la transcription": None,
        "verbose": True,  # <- Activation de l'affichage pendant la transcription
        "temperature": (0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
    }

    if accurate:
        defaults.update({"beam_size": 5, "best_of": 5})
    else:
        defaults.update({"beam_size": None, "best_of": None})

    kwargs.pop("use_gpu", None)
    kwargs.pop("punctuations_with_words", None)
    params = {k: v for k, v in defaults.items() if v is not None}
    params.update(kwargs)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_to_load = model_name or config.whisper_model
    logging.info(f"Chargement du modèle {model_to_load} sur {device}")
    progress_queue.put({"value": 20, "status_text": f"Transcription sur {device}..."})
    model = whisper.load_model(model_to_load, device=device)

    try:
        result = whisper.transcribe(model, audio_path, **params)
    except AssertionError as ae:
        logging.warning("Timestamped failed (%s), fallback transcription.", ae)
        basic = model.transcribe(
            audio_path,
            language=language,
            beam_size=params.get("beam_size"),
            best_of=params.get("best_of"),
            temperature=params.get("temperature")
        )
        result = {"language": basic["language"], "segments": basic["segments"]}

    _write_all_outputs(result, base_name)
    return result


def transcribe_audio(
    audio_path: str,
    base_name: str,
    model_name: Optional[str] = None,
    accurate: bool = False,
    vad_method: str = "silero:v3.1",
    language: Optional[str] = None,
    **extra
) -> Dict:
    progress_queue.put({"value": 10, "status_text": "📥 Chargement du modèle Whisper..."})
    return run_transcription(
        audio_path=audio_path,
        base_name=base_name,
        model_name=model_name,
        accurate=accurate,
        vad_method=vad_method,
        language=language,
        **extra
    )


def transcribe_vocal(
    audio_path: str,
    base_name: str,
    model_name: Optional[str] = None,
    accurate: bool = False,
    **extra
) -> Dict:
    return transcribe_audio(
        audio_path=audio_path,
        base_name=base_name,
        model_name=model_name,
        accurate=accurate,
        **extra
    )
