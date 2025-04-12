import whisper_timestamped as whisper
import datetime
import os
import json
import csv
import torch
from utils import progress_queue, config  # ✅ import config
import logging
logging.getLogger("huggingface_hub.file_download").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub.utils").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
from model_downloader import download_whisper_model


progress_queue.put({
    'value': 10,
    'status_text': "📥 Téléchargement du modèle Whisper..."
})

def format_time(seconds):
    milliseconds = int((seconds - int(seconds)) * 1000)
    seconds = int(seconds)
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def clean_text(text):
    cleaned_text = text.replace("B:", "").replace("C:", "").replace("A:", "")
    return cleaned_text.strip()

def convert_transcription_to_srt(transcription, srt_path):
    with open(srt_path, 'w', encoding='utf-8') as srt_file:
        for i, segment in enumerate(transcription['segments']):
            start_time = format_time(segment['start'])
            end_time = format_time(segment['end'])
            text = clean_text(segment['text'])
            srt_file.write(f"{i+1}\n")
            srt_file.write(f"{start_time} --> {end_time}\n")
            srt_file.write(f"{text.strip()}\n\n")

def convert_transcription_to_vtt(transcription, vtt_path):
    with open(vtt_path, 'w', encoding='utf-8') as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for i, segment in enumerate(transcription['segments']):
            start_time = format_time(segment['start']).replace(',', '.')
            end_time = format_time(segment['end']).replace(',', '.')
            text = clean_text(segment['text'])
            vtt_file.write(f"{start_time} --> {end_time}\n")
            vtt_file.write(f"{text.strip()}\n\n")

def convert_transcription_to_csv(transcription, csv_path):
    with open(csv_path, 'w', encoding='utf-8', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Start Time", "End Time", "Text"])
        for segment in transcription['segments']:
            start_time = format_time(segment['start'])
            end_time = format_time(segment['end'])
            text = clean_text(segment['text'])
            writer.writerow([start_time, end_time, text])

def convert_transcription_to_tsv(transcription, tsv_path):
    with open(tsv_path, 'w', encoding='utf-8', newline='') as tsv_file:
        writer = csv.writer(tsv_file, delimiter='\t')
        writer.writerow(["Start Time", "End Time", "Text"])
        for segment in transcription['segments']:
            start_time = format_time(segment['start'])
            end_time = format_time(segment['end'])
            text = clean_text(segment['text'])
            writer.writerow([start_time, end_time, text])

def transcribe_segments_with_whisper(segment_files, pyannote_timestamps, accurate=False, **kwargs):
    # À implémenter si besoin de transcrire plusieurs segments avec timestamps externes
    pass

def transcribe_audio(audio_path, transcript_base_name, model_name=None, accurate=False, use_gpu=None, **kwargs):
    """
    Transcrit un fichier audio avec le modèle Whisper spécifié (compatible avec whisper_timestamped).
    """
    import whisper_timestamped as whisper

    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

    if model_name is None:
        model_name = "large-v3"
    logging.info(f"ℹ️ Modèle sélectionné pour la transcription: {model_name}")

    if use_gpu is None:
        use_gpu = torch.cuda.is_available()
    device = "cuda" if use_gpu else "cpu"

    if device == "cpu" and ("large" in model_name or "turbo" in model_name):
        logging.info(f"💡 Modèle {model_name} trop lourd pour CPU, remplacement par 'small'")
        model_name = "small"

    progress_queue.put({
        "value": 20,
        "status_text": f"Chargement du modèle {model_name}..."
    })

    logging.info(f"🚀 Chargement du modèle {model_name} sur {device}")
    model = whisper.load_model(model_name, device=device)

    progress_queue.put({
        "value": 30,
        "status_text": f"Transcription en cours avec {model_name}..."
    })

    # Options plus précises si "accurate"
    if accurate:
        kwargs['beam_size'] = 5
        kwargs['best_of'] = 5
        kwargs['temperature'] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        kwargs.pop('accurate', None)

    result = whisper.transcribe(model, audio_path, **kwargs)

    with open(f"{transcript_base_name}.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    convert_transcription_to_srt(result, f"{transcript_base_name}.srt")
    convert_transcription_to_vtt(result, f"{transcript_base_name}.vtt")
    convert_transcription_to_csv(result, f"{transcript_base_name}.csv")
    convert_transcription_to_tsv(result, f"{transcript_base_name}.tsv")

    logging.info(f"✅ Transcription enregistrée sous {transcript_base_name} aux formats .json/.srt/.vtt/.csv/.tsv")

    return result

def run_transcription(model, audio_path, transcript_base_name, **kwargs):
    if 'accurate' in kwargs and kwargs['accurate']:
        kwargs['beam_size'] = 5
        kwargs['best_of'] = 5
        kwargs['temperature'] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        del kwargs['accurate']

    default_params = {
        "language": None,
        "task": "transcribe",
        "beam_size": None,
        "best_of": None,
        "temperature": 0.0,
        "vad": False,
        "detect_disfluencies": False,
        "compute_word_confidence": True,
        "include_punctuation_in_confidence": False,
        "refine_whisper_precision": 0.5,
        "min_word_duration": 0.02,
        "trust_whisper_timestamps": True,
        "remove_empty_words": False,
        "plot_word_alignment": False,
        "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0,
        "no_speech_threshold": 0.6,
        "condition_on_previous_text": True,
        "initial_prompt": None,
        "suppress_tokens": "-1",
        "fp16": None,
        "verbose": False
    }

    for key, value in default_params.items():
        if key not in kwargs:
            kwargs[key] = value

    result = whisper.transcribe(model, audio_path, **kwargs)

    transcript_json_path = f"{transcript_base_name}.json"
    with open(transcript_json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    convert_transcription_to_srt(result, f"{transcript_base_name}.srt")
    convert_transcription_to_vtt(result, f"{transcript_base_name}.vtt")
    convert_transcription_to_csv(result, f"{transcript_base_name}.csv")
    convert_transcription_to_tsv(result, f"{transcript_base_name}.tsv")

    print(f"Transcription completed and saved to {transcript_base_name} in various formats.")

def transcribe_vocal(audio_path, transcript_base_name, model_name='openai/whisper-large-v3-turbo', accurate=False, use_gpu=None, **kwargs):
    transcribe_audio(
        audio_path=audio_path,
        transcript_base_name=transcript_base_name,
        model_name=model_name,
        accurate=accurate,
        use_gpu=use_gpu,
        **kwargs
    )
