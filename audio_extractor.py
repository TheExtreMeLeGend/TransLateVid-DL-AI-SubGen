import subprocess
import os
import shutil
from pydub import AudioSegment
import logging
import soundfile as sf
import librosa
import numpy as np
import tempfile
import torch
import threading

from utils import config  # ✅ Ajouté pour lire l'état du multi-threading

# Filtrage pour ne logguer que les messages pertinents dans la console
class SpecificMessageFilter(logging.Filter):
    def filter(self, record):
        return any(keyword in record.getMessage().lower() for keyword in [
            "separated", "audio separation completed", "vocals", "accompaniment"
        ])

# Configuration du logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.addFilter(SpecificMessageFilter())
logger.addHandler(ch)

fh = logging.FileHandler('error.log', encoding='utf-8')
fh.setLevel(logging.ERROR)
logger.addHandler(fh)

def extract_audio(video_file, output_audio_file):
    command = f'ffmpeg -i "{video_file}" -q:a 0 -map a -y "{output_audio_file}"'
    subprocess.run(command, shell=True, check=True)

def resample_audio(input_path, output_path, target_samplerate):
    if os.path.exists(input_path):
        y, sr = librosa.load(input_path, sr=None)
        y_resampled = librosa.resample(y, orig_sr=sr, target_sr=target_samplerate)
        sf.write(output_path, y_resampled, target_samplerate)
    else:
        raise FileNotFoundError(f"File not found: {input_path}")

def combine_tracks(tracks, output_path):
    combined = None
    for track in tracks:
        if os.path.exists(track):
            data, samplerate = sf.read(track)
            if combined is None:
                combined = data
            else:
                combined += data
        else:
            raise FileNotFoundError(f"File not found: {track}")
    sf.write(output_path, combined, samplerate)

def create_empty_track(file_path, sample_rate=44100):
    sf.write(file_path, np.zeros((1,)), sample_rate)

def is_file_empty(file_path):
    data, _ = sf.read(file_path)
    return len(data) == 0

def run_demucs_with_logs(command_args):
    process = subprocess.Popen(
        command_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    def stream_output():
        for line in process.stdout:
            if line.strip():
                logging.info(line.strip())

    thread = threading.Thread(target=stream_output)
    thread.start()
    process.wait()
    thread.join()

def separate_audio(input_file, output_dir, use_gpu=None, use_threading=None):
    if use_gpu is None:
        use_gpu = torch.cuda.is_available()
    if use_threading is None:
        use_threading = config.use_threading  # ✅ Lecture de la config globale

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Dossier de sortie créé: {output_dir}")

    logging.info(f"Début de la séparation audio - Fichier source: {input_file}")
    logging.info(f"Dossier de sortie: {output_dir}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_input = os.path.join(temp_dir, "temp_audio.mp3")
        shutil.copy(input_file, temp_input)
        logging.info(f"Fichier audio temporaire créé: {temp_input}")

        if not os.path.exists(temp_input):
            raise FileNotFoundError(f"Fichier audio temporaire introuvable: {temp_input}")

        device = "cuda" if use_gpu else "cpu"
        logging.info(f"🧠 Tentative de séparation audio avec {device.upper()}...")

        try:
            command = [
                "demucs",
                "--two-stems=vocals",
                "-n", "mdx_extra_q",
                "-d", device,
                temp_input
            ]

            logging.info(f"Exécution de Demucs avec la commande: {' '.join(command)}")

            # ✅ Utilisation du threading ou pas selon la config
            if use_threading:
                run_demucs_with_logs(command)
            else:
                result = subprocess.run(command, capture_output=True, text=True)
                logging.info(result.stdout)

            base_output_dir = os.path.join(os.getcwd(), "separated", "mdx_extra_q")
            logging.info(f"Recherche des fichiers séparés dans: {base_output_dir}")
            possible_dirs = [
                os.path.join(base_output_dir, "temp_audio"),
                os.path.join(base_output_dir, os.path.splitext(os.path.basename(temp_input))[0])
            ]
            temp_output_subdir = None
            for dir_path in possible_dirs:
                if os.path.exists(dir_path):
                    temp_output_subdir = dir_path
                    logging.info(f"Dossier de sortie Demucs trouvé: {temp_output_subdir}")
                    break

            if not temp_output_subdir or not os.path.exists(temp_output_subdir):
                if os.path.exists(base_output_dir):
                    logging.info(f"Contenu du dossier: {os.listdir(base_output_dir)}")
                raise FileNotFoundError("Le modèle de sortie de demucs n'a pas été trouvé.")

            logging.info(f"Fichiers à copier: {os.listdir(temp_output_subdir)}")
            for filename in os.listdir(temp_output_subdir):
                src_path = os.path.join(temp_output_subdir, filename)
                dst_path = os.path.join(output_dir, filename)
                try:
                    shutil.copy2(src_path, dst_path)
                    logging.info(f"Fichier copié avec succès: {src_path} -> {dst_path}")
                except Exception as e:
                    logging.error(f"Erreur lors de la copie de {src_path} vers {dst_path}: {e}")
                    try:
                        with open(src_path, 'rb') as src_file:
                            with open(dst_path, 'wb') as dst_file:
                                dst_file.write(src_file.read())
                        logging.info(f"Fichier copié avec méthode alternative: {dst_path}")
                    except Exception as alt_e:
                        logging.error(f"Échec de la méthode alternative: {alt_e}")

            logging.info(f"Fichiers dans le dossier de sortie après copie: {os.listdir(output_dir)}")

            if os.path.exists(os.path.join(output_dir, 'no_vocals.wav')) and not os.path.exists(os.path.join(output_dir, 'accompaniment.wav')):
                shutil.copy2(os.path.join(output_dir, 'no_vocals.wav'), os.path.join(output_dir, 'accompaniment.wav'))
                logging.info("Fichier 'no_vocals.wav' copié en 'accompaniment.wav'")

            for track_name in ['vocals', 'drums', 'bass', 'other']:
                track_path = os.path.join(output_dir, f'{track_name}.wav')
                if not os.path.exists(track_path) or is_file_empty(track_path):
                    create_empty_track(track_path)
                    logging.info(f"Piste vide créée: {track_path}")

            vocals_path = os.path.join(output_dir, 'vocals.wav')
            accompaniment_path = os.path.join(output_dir, 'accompaniment.wav')

            if not os.path.exists(accompaniment_path):
                try:
                    combine_tracks([
                        os.path.join(output_dir, 'drums.wav'),
                        os.path.join(output_dir, 'bass.wav'),
                        os.path.join(output_dir, 'other.wav')
                    ], accompaniment_path)
                    logging.info(f"Piste d'accompagnement créée: {accompaniment_path}")
                except Exception as e:
                    logging.error(f"Erreur lors de la création de la piste d'accompagnement: {e}")
                    create_empty_track(accompaniment_path)
                    logging.info("Piste d'accompagnement vide créée par défaut")

            try:
                vocals_44khz = os.path.join(output_dir, 'vocals_44khz.wav')
                if os.path.exists(vocals_path):
                    resample_audio(vocals_path, vocals_44khz, 44100)
                    logging.info(f"Piste vocals rééchantillonnée à 44.1kHz: {vocals_44khz}")
                    resample_audio(vocals_path, vocals_path, 16000)
                    logging.info(f"Piste vocals rééchantillonnée à 16kHz: {vocals_path}")
                else:
                    logging.error(f"Impossible de rééchantillonner: {vocals_path} n'existe pas")
            except Exception as e:
                logging.error(f"Erreur lors du rééchantillonnage: {e}")

            logging.info(f"Audio separation completed successfully! Output saved in {output_dir}")
            logging.info(f"Vocals track path: {vocals_path}")
            logging.info(f"Accompaniment track path: {accompaniment_path}")

        except subprocess.CalledProcessError as e:
            logging.error(f"Erreur lors de l'exécution de Demucs: {str(e)}")
            _create_fallback_tracks(input_file, output_dir)
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            logging.error("Tentative de fallback...")
            _create_fallback_tracks(input_file, output_dir)

# Le reste (fallback + convert_audio_to_16k) reste inchangé
