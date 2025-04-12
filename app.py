#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Application principale SRT Translator and Video Processor avec support multi-thread.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
from tkinter.ttk import Combobox
import os
import logging

# Supprimer tous les logs inutiles Hugging Face
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub.file_download").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub.utils").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.WARNING)
# Configuration simple et lisible des logs
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger("numba").setLevel(logging.WARNING)

# Niveau global des logs
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Désactiver les logs très verbeux
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub.file_download").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub.utils").setLevel(logging.ERROR)
import threading
import queue

# Importer les modules personnalisés
from utils import setup_logger, config, command_queue, open_file, clear_log_file
from ui_components import ProgressWindow, ResultDialog
# Import both processors - just once
from video_processor import VideoProcessor, ThreadedVideoProcessor

class SRTTranslatorApp:
    """Application principale pour traduire et traiter les vidéos."""

    def __init__(self):
        """Initialise l'interface utilisateur de l'application."""
        self.root = tk.Tk()
        self.root.title("SRT Translator and Video Processor")
        self.root.geometry("850x850")
        # Configuration du thème
        style = ttk.Style(self.root)
        style.theme_use("clam")

        # IMPORTANT: Initialize use_threading before _create_ui is called
        self.use_threading = tk.BooleanVar(value=True)  # Option pour activer/désactiver le multi-threading

        # Création de l'interface utilisateur
        self._create_ui()

        # Processeur de vidéos
        self._update_processor()

        # Configuration du listener de commandes
        self._setup_command_listener()

    def _update_processor(self):
        """Met à jour le processeur en fonction de l'option de threading."""
        if self.use_threading.get():
            self.processor = ThreadedVideoProcessor(config)
            logging.info("Mode multi-thread activé")
        else:
            self.processor = VideoProcessor(config)
            logging.info("Mode multi-thread désactivé")
        
        # Mettre à jour le client API
        self.processor.update_api_client()

    def _create_ui(self):
        """Crée l'interface utilisateur principale."""
        main_frame = tk.Frame(self.root, bg="#ffffff", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="SRT Translator and Video Processor", font=("Helvetica", 16, "bold"), bg="#ffffff").grid(row=0, column=0, columnspan=2, pady=(10, 20))

        labels_entries = [
            ("Enter video URL:", "url_entry"),
            ("Enter DeepL API Key:", "deepl_key_entry"),
            ("Enter OpenAI API Key:", "openai_key_entry")
        ]

        for i, (label, attr) in enumerate(labels_entries, start=1):
            tk.Label(main_frame, text=label, bg="#ffffff", font=("Helvetica", 10)).grid(row=i, column=0, sticky="w", pady=5)
            setattr(self, attr, tk.Entry(main_frame, font=("Helvetica", 10), width=40))
            getattr(self, attr).grid(row=i, column=1, pady=5, padx=(10, 0))

        tk.Label(main_frame, text="Select target language:", bg="#ffffff", font=("Helvetica", 10)).grid(row=4, column=0, sticky="w", pady=(15, 5))
        self.language_combobox = Combobox(main_frame, values=[
            "FR - French", "EN - English", "ES - Spanish", "DE - German", "IT - Italian",
            "ZH - Chinese", "JA - Japanese", "RU - Russian", "NL - Dutch",
            "PT - Portuguese", "AR - Arabic", "HI - Hindi", "KO - Korean", "TR - Turkish"
        ], font=("Helvetica", 10), state="readonly", width=37)
        self.language_combobox.grid(row=4, column=1, pady=(15, 5), padx=(10, 0))

        tk.Label(main_frame, text="Select translation service:", bg="#ffffff", font=("Helvetica", 10)).grid(row=5, column=0, sticky="w", pady=(15, 5))
        self.service_combobox = Combobox(main_frame, values=["ChatGPT", "DeepL"], font=("Helvetica", 10), state="readonly", width=37)
        self.service_combobox.grid(row=5, column=1, pady=(15, 5), padx=(10, 0))

        tk.Label(main_frame, text="Select Whisper Model:", bg="#ffffff", font=("Helvetica", 10)).grid(row=6, column=0, sticky="w", pady=(15, 5))
        whisper_frame = tk.Frame(main_frame, bg="#ffffff")
        whisper_frame.grid(row=6, column=1, pady=(15, 5), padx=(10, 0), sticky="w")

        self.gpu_var = tk.BooleanVar(value=config.is_cuda_available())
        tk.Checkbutton(whisper_frame, text="Utiliser le GPU (NVIDIA)", variable=self.gpu_var, bg="#ffffff", font=("Helvetica", 10)).pack(side="left")
        self.whisper_model_combobox = Combobox(whisper_frame, values=[
            "tiny", "base", "small", "medium", "large", "large-v3-turbo"
        ], font=("Helvetica", 10), state="readonly", width=20)
        self.whisper_model_combobox.pack(side="left", padx=(10, 0))
        self.whisper_model_combobox.set(config.whisper_model)

        self.model_resources = {
            "tiny": {"RAM": "2GB", "VRAM": "1GB"},
            "base": {"RAM": "4GB", "VRAM": "2GB"},
            "small": {"RAM": "6GB", "VRAM": "3GB"},
            "medium": {"RAM": "10GB", "VRAM": "5GB"},
            "large": {"RAM": "16GB", "VRAM": "8GB"},
            "large-v3-turbo": {"RAM": "20GB", "VRAM": "10GB"}
        }

        self.resource_label = tk.Label(main_frame, text="", bg="#ffffff", font=("Helvetica", 9, "italic"))
        self.resource_label.grid(row=7, column=1, sticky="w", pady=(0, 10), padx=(10, 0))

        def update_resource_info(event):
            model = self.whisper_model_combobox.get()
            info = self.model_resources.get(model, {"RAM": "?", "VRAM": "?"})
            self.resource_label.config(text=f"Estimated: RAM {info['RAM']} / VRAM {info['VRAM']}")

        self.whisper_model_combobox.bind("<<ComboboxSelected>>", update_resource_info)
        update_resource_info(None)

        # Ajout de l'option de multi-threading
        threading_frame = tk.Frame(main_frame, bg="#ffffff")
        threading_frame.grid(row=8, column=0, columnspan=2, pady=(15, 5), sticky="w")
        
        tk.Checkbutton(
            threading_frame, 
            text="Activer le traitement multi-thread (plus rapide mais consomme plus de ressources)", 
            variable=self.use_threading, 
            command=self._update_processor,
            bg="#ffffff", 
            font=("Helvetica", 10)
        ).pack(side="left", padx=(10, 0))

        tk.Button(main_frame, text="Process Video", command=self._process_video, font=("Helvetica", 12, "bold"), bg="#2196F3", fg="white", padx=20, pady=10).grid(row=9, column=0, columnspan=2, pady=(30, 10))

        self._create_menu()
        self._load_defaults()
        self.main_frame = main_frame

    def _create_menu(self):
        """Crée le menu de l'application."""
        menubar = tk.Menu(self.root)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Select Video File", command=self._select_local_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Menu Logs
        logs_menu = tk.Menu(menubar, tearoff=0)
        logs_menu.add_command(label="Open Log File", command=lambda: open_file(os.path.join('logs', 'app.log')))
        logs_menu.add_command(label="Clear Logs", command=clear_log_file)
        menubar.add_cascade(label="Logs", menu=logs_menu)
        
        # Menu Settings
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_checkbutton(label="Use Multi-Threading", variable=self.use_threading, command=self._update_processor)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        
        # Menu Aide
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Help", command=self._show_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def _load_defaults(self):
        """Charge les valeurs par défaut dans l'interface."""
        # Charger les clés API
        self.deepl_key_entry.insert(0, config.deepl_key)
        self.openai_key_entry.insert(0, config.openai_key)
        
        # Sélectionner les valeurs par défaut dans les combobox
        if not self.language_combobox.get():
            self.language_combobox.set(config.default_language)
        if not self.service_combobox.get():
            self.service_combobox.set(config.default_service)
    
    def _setup_command_listener(self):
        """Configure le listener de commandes venant du thread de traitement."""
        def check_commands():
            try:
                # Vérifier s'il y a des commandes dans la queue
                try:
                    cmd = command_queue.get_nowait()
                    self._handle_command(cmd)
                except queue.Empty:
                    pass
                
                # Programmer la prochaine vérification
                self.root.after(100, check_commands)
            except Exception as e:
                logging.error(f"Erreur dans le listener de commandes: {e}")
                # Réessayer
                self.root.after(1000, check_commands)
        
        # Démarrer la vérification des commandes
        self.root.after(100, check_commands)
    
    def _handle_command(self, cmd):
        """Traite une commande provenant de la queue."""
        command = cmd.get("command")
        
        if command == "processing_done":
            # Traitement terminé avec succès
            video_folder = cmd.get("video_folder")
            self._handle_processing_done(video_folder)
            
        elif command == "processing_cancelled":
            # Traitement annulé par l'utilisateur
            self._handle_processing_cancelled()
            
        elif command == "error":
            # Traitement terminé avec une erreur
            error_message = cmd.get("message")
            self._handle_processing_error(error_message)
    
    def _process_video(self, video_path=None):
        """Démarre le traitement d'une vidéo."""
        url = self.url_entry.get()
        deepl_key = self.deepl_key_entry.get()
        openai_key = self.openai_key_entry.get()
        
        # Mettre à jour la configuration
        config.deepl_key = deepl_key
        config.openai_key = openai_key
        config.save_api_keys()
        
        # Récupérer et sauvegarder le modèle Whisper sélectionné
        whisper_model = self.whisper_model_combobox.get()
        if whisper_model:
            config.whisper_model = whisper_model
            config.save_config()
            logging.info(f"Modèle Whisper sélectionné: {whisper_model}")
        
        # Mettre à jour le client OpenAI
        self.processor.update_api_client()
        
        # Récupérer l'état de l'option GPU
        use_gpu = self.gpu_var.get() and config.is_cuda_available()
        
        if not url and not video_path:
            messagebox.showwarning("Erreur d'entrée", "Veuillez entrer une URL ou sélectionner un fichier vidéo.")
            return

        target_language = self.language_combobox.get().split(' - ')[0]
        translation_service = self.service_combobox.get()
        if not target_language:
            messagebox.showwarning("Erreur d'entrée", "Veuillez sélectionner une langue cible.")
            return

        # Créer la fenêtre de progression
        self.progress_window = ProgressWindow(self.root, "Traitement de la vidéo")
        self.progress_window.update_progress_ui(0, "Initialisation du traitement...")
        
        # Démarrer le traitement
        self.processor.process_video(url, video_path, target_language, translation_service, use_gpu)
    
    def _select_local_file(self):
        """Sélectionne un fichier vidéo local à traiter."""
        file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.mkv;*.avi;*.mov")])
        if file_path:
            self._process_video(video_path=file_path)
    
    def _handle_processing_done(self, video_folder):
        """Gère la fin de traitement réussie."""
        try:
            # Fermer la fenêtre de progression
            self.progress_window.close()
            
            # Afficher la boîte de dialogue de résultat
            message = "Le traitement s'est terminé avec succès!\n\nTous les fichiers ont été enregistrés dans le dossier ci-dessous:"
            result_dialog = ResultDialog(self.root, "Traitement terminé", message, video_folder)
            result_dialog.show()
            
        except Exception as e:
            logging.error(f"Erreur en fin de traitement: {e}", exc_info=True)
            messagebox.showinfo("Information", f"Le traitement est terminé.\nLes fichiers se trouvent dans:\n{video_folder}")
    
    def _handle_processing_cancelled(self):
        """Gère l'annulation du traitement."""
        try:
            self.progress_window.close()
            messagebox.showinfo("Traitement annulé", "Le traitement a été annulé par l'utilisateur.")
        except Exception as e:
            logging.error(f"Erreur lors de l'annulation: {e}")
    
    def _handle_processing_error(self, error_message):
        """Gère une erreur de traitement."""
        try:
            self.progress_window.close()
            messagebox.showerror("Erreur", f"Une erreur s'est produite : {error_message}")
        except Exception as e:
            logging.error(f"Erreur lors de l'affichage de l'erreur: {e}")
    
    def _show_about(self):
        """Affiche la boîte de dialogue À propos."""
        messagebox.showinfo(
            "À propos", 
            "SRT Translator and Video Processor\n\n"
            "Version 1.1\n\n"
            "Une application pour télécharger des vidéos, extraire l'audio, "
            "séparer les pistes audio, transcrire et traduire les sous-titres.\n\n"
            "Mode multi-thread ajouté pour des performances améliorées."
        )
    
    def _show_help(self):
        """Affiche l'aide de l'application."""
        help_text = (
            "Comment utiliser l'application:\n\n"
            "1. Entrez une URL de vidéo ou sélectionnez un fichier local\n"
            "2. Configurez les clés API pour DeepL et/ou OpenAI\n"
            "3. Sélectionnez la langue cible et le service de traduction\n"
            "4. Activez/désactivez le mode multi-thread selon vos besoins\n"
            "5. Cliquez sur 'Process Video'\n\n"
            "Note: Le mode multi-thread est plus rapide mais utilise plus de ressources système."
        )
        messagebox.showinfo("Aide", help_text)
    
    def run(self):
        """Lance l'application."""
        # Journaliser le démarrage de l'application
        logging.info("=== Application démarrée (avec support multi-thread) ===")
        if config.is_cuda_available():
            logging.info(f"GPU détecté: {config.get_gpu_name()}")
        else:
            logging.info("Aucun GPU compatible CUDA détecté, utilisation du CPU uniquement")
        
        # Démarrer la boucle principale
        self.root.mainloop()

def main():
    """Point d'entrée principal de l'application."""
    # Configuration des logs
    setup_logger()
    
    try:
        # Créer et démarrer l'application
        app = SRTTranslatorApp()
        app.run()
    except Exception as e:
        logging.critical(f"Erreur critique: {str(e)}", exc_info=True)
        messagebox.showerror("Erreur critique", f"Une erreur inattendue s'est produite: {str(e)}")

if __name__ == "__main__":
    main()
