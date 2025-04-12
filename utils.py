#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour les fonctions utilitaires, la configuration et le logging.
"""

import os
import json
import logging
import queue
import io
import sys
import platform
import subprocess
import torch

# Queues pour la communication entre les threads
log_queue = queue.Queue()
progress_queue = queue.Queue()
command_queue = queue.Queue()

# Fichiers de configuration
KEYS_FILE = "api_keys.json"
CONFIG_FILE = "config.json"

class LockMessageFilter(logging.Filter):
    """Filtre qui bloque les messages liés aux verrous."""
    def filter(self, record):
        if hasattr(record, 'getMessage'):
            message = record.getMessage().lower()
            if 'lock' in message and ('attempting to acquire' in message or 'not acquired' in message):
                return False
        return True

class LoggingRedirector(io.StringIO):
    """Redirige stdout et stderr vers le logger."""
    def __init__(self, logger, level):
        super().__init__()
        self.logger = logger
        self.level = level
        self.buffer = ""

    def write(self, string):
        if not string or string.isspace():
            return
        self.buffer += string
        if string.endswith('\n'):
            self.logger.log(self.level, self.buffer.rstrip())
            self.buffer = ""

    def flush(self):
        if self.buffer:
            self.logger.log(self.level, self.buffer)
            self.buffer = ""

class QueueHandler(logging.Handler):
    """Handler qui met les logs dans une queue pour affichage GUI."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)

# Variables de redirection stdout/stderr
original_stdout = None
original_stderr = None

def setup_logger():
    """Configure le logger principal."""
    global original_stdout, original_stderr

    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Désactiver complètement les logs de verrou huggingface
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub.file_download").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub.utils").setLevel(logging.ERROR)

    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(log_formatter)
    queue_handler.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(os.path.join('logs', 'app.log'), encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG)

    # Appliquer le filtre de messages de lock à tous les handlers
    lock_filter = LockMessageFilter()
    queue_handler.addFilter(lock_filter)
    file_handler.addFilter(lock_filter)
    console_handler.addFilter(lock_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(queue_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = LoggingRedirector(root_logger, logging.INFO)
    sys.stderr = LoggingRedirector(root_logger, logging.WARNING)

def restore_std_redirects():
    sys.stdout = original_stdout
    sys.stderr = original_stderr

def enable_std_redirects():
    root_logger = logging.getLogger()
    sys.stdout = LoggingRedirector(root_logger, logging.INFO)
    sys.stderr = LoggingRedirector(root_logger, logging.WARNING)

class Config:
    """Gère la configuration et les clés API de l'application."""
    def __init__(self):
        self.deepl_key = ""
        self.openai_key = ""
        self.default_language = "FR - French"
        self.default_service = "ChatGPT"
        self.use_gpu = torch.cuda.is_available()
        self.output_folder = "output"
        self.whisper_model = "large-v3-turbo"
        self.use_threading = True
        self.load_config()

    def load_api_keys(self):
        if os.path.exists(KEYS_FILE):
            try:
                with open(KEYS_FILE, 'r') as file:
                    keys = json.load(file)
                    self.deepl_key = keys.get("deepl_key", "")
                    self.openai_key = keys.get("openai_key", "")
                    logging.info("Clés API chargées avec succès")
                    return True
            except Exception as e:
                logging.error(f"Erreur lors du chargement des clés API: {str(e)}")
        return False

    def save_api_keys(self):
        try:
            keys = {"deepl_key": self.deepl_key, "openai_key": self.openai_key}
            with open(KEYS_FILE, 'w') as file:
                json.dump(keys, file)
            logging.info("Clés API sauvegardées avec succès")
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde des clés API: {str(e)}")
            return False

    def load_config(self):
        self.load_api_keys()
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as file:
                    config = json.load(file)
                    self.default_language = config.get("default_language", self.default_language)
                    self.default_service = config.get("default_service", self.default_service)
                    self.use_gpu = config.get("use_gpu", self.use_gpu)
                    self.output_folder = config.get("output_folder", self.output_folder)
                    self.whisper_model = config.get("whisper_model", self.whisper_model)
                    self.use_threading = config.get("use_threading", self.use_threading)
                logging.info("Configuration chargée avec succès")
            except Exception as e:
                logging.error(f"Erreur lors du chargement de la configuration: {str(e)}")

    def save_config(self):
        self.save_api_keys()
        try:
            config = {
                "default_language": self.default_language,
                "default_service": self.default_service,
                "use_gpu": self.use_gpu,
                "output_folder": self.output_folder,
                "whisper_model": self.whisper_model,
                "use_threading": self.use_threading
            }
            with open(CONFIG_FILE, 'w') as file:
                json.dump(config, file)
            logging.info("Configuration sauvegardée avec succès")
            return True
        except Exception as e:
            logging.error(f"Erreur lors de la sauvegarde de la configuration: {str(e)}")
            return False

    @staticmethod
    def is_cuda_available():
        return torch.cuda.is_available()

    @staticmethod
    def get_gpu_name():
        return torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Aucun GPU détecté"

def open_folder(path):
    logging.info(f"Tentative d'ouverture du dossier: {path}")
    if not os.path.exists(path):
        logging.error(f"Impossible d'ouvrir le dossier: {path}")
        return False
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path], check=True)
        else:
            subprocess.run(["xdg-open", path], check=True)
        logging.info(f"Dossier ouvert: {path}")
        return True
    except Exception as e:
        logging.error(f"Erreur lors de l'ouverture du dossier {path}: {e}")
        return False

def open_file(file_path):
    if os.path.exists(file_path):
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", file_path])
        else:
            subprocess.Popen(["xdg-open", file_path])
        return True
    else:
        logging.error(f"Fichier introuvable: {file_path}")
        return False

def clear_log_file():
    try:
        with open(os.path.join('logs', 'app.log'), "w") as f:
            f.write("")
        logging.info("Le fichier de logs a été effacé")
        return True
    except Exception as e:
        logging.error(f"Impossible d'effacer le fichier de logs: {str(e)}")
        return False
    
def format_whisper_model_name(model_name):
    """Convertit le nom du modèle Whisper au format attendu par la bibliothèque."""
    if model_name and not model_name.startswith("openai/whisper-"):
        return f"openai/whisper-{model_name}"
    return model_name

# Créer une instance globale unique
config = Config()