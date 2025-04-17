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
from PIL import Image, ImageTk
import webbrowser

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
from video_processor import VideoProcessor



# Définition des couleurs
COLORS = {
    "primary": "#3f51b5",      # Bleu principal
    "primary_dark": "#303f9f", # Bleu foncé pour survol
    "secondary": "#ff4081",    # Rose accentuation
    "background": "#f5f5f7",   # Gris très clair
    "card_bg": "#ffffff",      # Blanc pour les cartes
    "text": "#212121",         # Texte principal presque noir
    "text_secondary": "#757575", # Texte secondaire gris
    "success": "#4caf50",      # Vert pour succès
    "warning": "#ff9800",      # Orange pour avertissements
    "error": "#f44336",        # Rouge pour erreurs
    "border": "#e0e0e0"        # Gris clair pour bordures
}

class ModernButton(tk.Button):
    """Bouton modernisé avec effets de survol"""
    def __init__(self, master=None, **kwargs):
        self.bg_color = kwargs.pop('bg', COLORS["primary"])
        self.hover_color = kwargs.pop('hover_color', COLORS["primary_dark"])
        kwargs['bg'] = self.bg_color
        kwargs['activebackground'] = self.hover_color
        kwargs['bd'] = kwargs.get('bd', 0)
        kwargs['relief'] = kwargs.get('relief', 'flat')
        kwargs['fg'] = kwargs.get('fg', 'white')
        kwargs['activeforeground'] = kwargs.get('activeforeground', 'white')
        kwargs['font'] = kwargs.get('font', ('Segoe UI', 10))
        super().__init__(master, **kwargs)
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
    
    def on_enter(self, e):
        self['bg'] = self.hover_color
        
    def on_leave(self, e):
        self['bg'] = self.bg_color

class ModernFrame(tk.Frame):
    """Frame avec bordure et ombre pour style carte"""
    def __init__(self, master=None, **kwargs):
        kwargs['bg'] = kwargs.get('bg', COLORS["card_bg"])
        kwargs['bd'] = kwargs.get('bd', 1)
        kwargs['relief'] = kwargs.get('relief', 'solid')
        kwargs['highlightbackground'] = kwargs.get('highlightbackground', COLORS["border"])
        kwargs['highlightthickness'] = kwargs.get('highlightthickness', 1)
        kwargs['padx'] = kwargs.get('padx', 15)
        kwargs['pady'] = kwargs.get('pady', 15)
        super().__init__(master, **kwargs)

class SRTTranslatorApp:
    """Application principale pour traduire et traiter les vidéos."""

    def __init__(self):
        """Initialise l'interface utilisateur de l'application."""
        self.root = tk.Tk()
        self.root.title("SRT Translator Pro")
        self.root.geometry("950x750")
        self.root.configure(bg=COLORS["background"])
        self.root.minsize(950, 850)
        
        # Configuration de la police par défaut
        self.default_font = ('Segoe UI', 10)
        
        # Configuration du thème
        style = ttk.Style(self.root)
        style.theme_use("clam")
        
        # Configure les styles personnalisés
        style.configure("TFrame", background=COLORS["background"])
        style.configure("Card.TFrame", background=COLORS["card_bg"])
        style.configure("TLabel", background=COLORS["card_bg"], font=self.default_font)
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Subheader.TLabel", font=("Segoe UI", 12))
        style.configure("TEntry", font=self.default_font)
        style.configure("TCheckbutton", background=COLORS["card_bg"], font=self.default_font)
        style.configure("TCombobox", font=self.default_font)

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
        # Conteneur principal avec padding
        main_container = tk.Frame(self.root, bg=COLORS["background"], padx=20, pady=20)
        main_container.pack(fill="both", expand=True)
        
        # Section d'en-tête avec logo et titre
        header_frame = tk.Frame(main_container, bg=COLORS["background"])
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Logo et titre
        try:
            # Remplacez par le chemin de votre logo si vous en avez un
            logo_img = Image.open("assets/logo.png").resize((48, 48))
            logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = tk.Label(header_frame, image=logo_photo, bg=COLORS["background"])
            logo_label.image = logo_photo  # Garde une référence
            logo_label.pack(side="left", padx=(0, 15))
        except:
            # Si pas d'image, on met juste un placeholder coloré
            logo_frame = tk.Frame(header_frame, width=48, height=48, bg=COLORS["primary"])
            logo_frame.pack(side="left", padx=(0, 15))

        title_frame = tk.Frame(header_frame, bg=COLORS["background"])
        title_frame.pack(side="left", fill="y")
        
        tk.Label(
            title_frame, 
            text="SRT Translator Pro", 
            font=("Segoe UI", 22, "bold"), 
            fg=COLORS["primary"], 
            bg=COLORS["background"]
        ).pack(anchor="w")
        
        tk.Label(
            title_frame, 
            text="Traduction et traitement vidéo avec IA", 
            font=("Segoe UI", 12), 
            fg=COLORS["text_secondary"], 
            bg=COLORS["background"]
        ).pack(anchor="w")
        
        # Cartes de contenu
        content_frame = tk.Frame(main_container, bg=COLORS["background"])
        content_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # Première colonne
        left_column = tk.Frame(content_frame, bg=COLORS["background"])
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Deuxième colonne
        right_column = tk.Frame(content_frame, bg=COLORS["background"])
        right_column.pack(side="right", fill="both", expand=True, padx=(10, 0))
        
        # --- SECTION SOURCES VIDÉO ---
        source_card = ModernFrame(left_column)
        source_card.pack(fill="x", pady=(0, 20))
        
        tk.Label(
            source_card, 
            text="Source Vidéo", 
            font=("Segoe UI", 14, "bold"), 
            bg=COLORS["card_bg"]
        ).pack(anchor="w", pady=(0, 15))
        
        # URL d'entrée avec icône
        url_frame = tk.Frame(source_card, bg=COLORS["card_bg"])
        url_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            url_frame, 
            text="URL de la vidéo:", 
            font=self.default_font, 
            bg=COLORS["card_bg"]
        ).pack(anchor="w")
        
        url_input_frame = tk.Frame(url_frame, bg=COLORS["card_bg"])
        url_input_frame.pack(fill="x", pady=(5, 0))
        
        self.url_entry = tk.Entry(
            url_input_frame, 
            font=self.default_font, 
            bd=1, 
            relief="solid"
        )
        self.url_entry.pack(side="left", fill="x", expand=True)
        
        browse_btn = ModernButton(
            url_input_frame, 
            text="Parcourir", 
            command=self._select_local_file,
            font=self.default_font,
            padx=10
        )
        browse_btn.pack(side="right", padx=(10, 0))
        
        # --- SECTION CONFIGURATION ---
        config_card = ModernFrame(left_column)
        config_card.pack(fill="x")
        
        tk.Label(
            config_card, 
            text="Configuration", 
            font=("Segoe UI", 14, "bold"), 
            bg=COLORS["card_bg"]
        ).pack(anchor="w", pady=(0, 15))
        
        # Section des API Keys
        api_frame = tk.Frame(config_card, bg=COLORS["card_bg"])
        api_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            api_frame, 
            text="Clés API", 
            font=("Segoe UI", 12), 
            bg=COLORS["card_bg"], 
            fg=COLORS["primary"]
        ).pack(anchor="w", pady=(0, 5))
        
        # DeepL API Key
        tk.Label(
            api_frame, 
            text="Clé API DeepL:", 
            bg=COLORS["card_bg"],
            font=self.default_font
        ).pack(anchor="w")
        
        self.deepl_key_entry = tk.Entry(
            api_frame, 
            font=self.default_font, 
            bd=1, 
            relief="solid", 
            show="•"
        )
        self.deepl_key_entry.pack(fill="x", pady=(5, 10))
        
        # OpenAI API Key
        tk.Label(
            api_frame, 
            text="Clé API OpenAI:", 
            bg=COLORS["card_bg"],
            font=self.default_font
        ).pack(anchor="w")
        
        self.openai_key_entry = tk.Entry(
            api_frame, 
            font=self.default_font, 
            bd=1, 
            relief="solid", 
            show="•"
        )
        self.openai_key_entry.pack(fill="x", pady=5)
        
        # Gestion des langues
        language_frame = tk.Frame(config_card, bg=COLORS["card_bg"])
        language_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            language_frame, 
            text="Langue et Traduction", 
            font=("Segoe UI", 12), 
            bg=COLORS["card_bg"], 
            fg=COLORS["primary"]
        ).pack(anchor="w", pady=(0, 5))
        
        # Langue cible
        tk.Label(
            language_frame, 
            text="Langue cible:", 
            bg=COLORS["card_bg"],
            font=self.default_font
        ).pack(anchor="w")
        
        self.language_combobox = ttk.Combobox(
            language_frame, 
            values=[
                "FR - French", "EN - English", "ES - Spanish", "DE - German", "IT - Italian",
                "ZH - Chinese", "JA - Japanese", "RU - Russian", "NL - Dutch",
                "PT - Portuguese", "AR - Arabic", "HI - Hindi", "KO - Korean", "TR - Turkish"
            ], 
            state="readonly", 
            font=self.default_font
        )
        self.language_combobox.pack(fill="x", pady=(5, 10))
        
        # Service de traduction
        tk.Label(
            language_frame, 
            text="Service de traduction:", 
            bg=COLORS["card_bg"],
            font=self.default_font
        ).pack(anchor="w")
        
        self.service_combobox = ttk.Combobox(
            language_frame, 
            values=["ChatGPT", "DeepL"], 
            state="readonly", 
            font=self.default_font
        )
        self.service_combobox.pack(fill="x", pady=5)
        
        # --- SECTION AVANCÉE (Colonne de droite) ---
        advanced_card = ModernFrame(right_column)
        advanced_card.pack(fill="x", pady=(0, 20))
        
        tk.Label(
            advanced_card, 
            text="Paramètres Avancés", 
            font=("Segoe UI", 14, "bold"), 
            bg=COLORS["card_bg"]
        ).pack(anchor="w", pady=(0, 15))
        
        # Configuration Whisper
        whisper_frame = tk.Frame(advanced_card, bg=COLORS["card_bg"])
        whisper_frame.pack(fill="x", pady=(0, 15))
        
        tk.Label(
            whisper_frame, 
            text="Modèle Whisper", 
            font=("Segoe UI", 12), 
            bg=COLORS["card_bg"], 
            fg=COLORS["primary"]
        ).pack(anchor="w", pady=(0, 5))
        
        # Option GPU
        gpu_frame = tk.Frame(whisper_frame, bg=COLORS["card_bg"])
        gpu_frame.pack(fill="x", pady=(5, 10))
        
        self.gpu_var = tk.BooleanVar(value=config.is_cuda_available())
        gpu_check = ttk.Checkbutton(
            gpu_frame, 
            text="Utiliser le GPU (NVIDIA)", 
            variable=self.gpu_var,
            style="TCheckbutton"
        )
        gpu_check.pack(side="left")
        
        # Si CUDA est indisponible
        if not config.is_cuda_available():
            disabled_label = tk.Label(
                gpu_frame, 
                text="(CUDA non disponible)", 
                fg=COLORS["error"],
                bg=COLORS["card_bg"],
                font=("Segoe UI", 9, "italic")
            )
            disabled_label.pack(side="left", padx=(5, 0))
        
        # Sélection du modèle
        tk.Label(
            whisper_frame, 
            text="Sélectionnez le modèle Whisper:", 
            bg=COLORS["card_bg"],
            font=self.default_font
        ).pack(anchor="w")
        
        model_frame = tk.Frame(whisper_frame, bg=COLORS["card_bg"])
        model_frame.pack(fill="x", pady=5)
        
        self.whisper_model_combobox = ttk.Combobox(
            model_frame, 
            values=[
                "tiny", "base", "small", "medium", "large", "large-v3-turbo"
            ], 
            state="readonly", 
            font=self.default_font
        )
        self.whisper_model_combobox.pack(side="left", fill="x", expand=True)
        
        # Tooltip sur les ressources
        self.model_resources = {
            "tiny": {"RAM": "2GB", "VRAM": "1GB"},
            "base": {"RAM": "4GB", "VRAM": "2GB"},
            "small": {"RAM": "6GB", "VRAM": "3GB"},
            "medium": {"RAM": "10GB", "VRAM": "5GB"},
            "large": {"RAM": "16GB", "VRAM": "8GB"},
            "large-v3-turbo": {"RAM": "20GB", "VRAM": "10GB"}
        }
        
        info_frame = tk.Frame(whisper_frame, bg=COLORS["card_bg"])
        info_frame.pack(fill="x", pady=(5, 0))
        
        self.resource_label = tk.Label(
            info_frame, 
            text="", 
            bg=COLORS["card_bg"], 
            font=("Segoe UI", 9, "italic"),
            fg=COLORS["text_secondary"]
        )
        self.resource_label.pack(anchor="w")
        
        def update_resource_info(event):
            model = self.whisper_model_combobox.get()
            info = self.model_resources.get(model, {"RAM": "?", "VRAM": "?"})
            self.resource_label.config(text=f"Ressources estimées: RAM {info['RAM']} / VRAM {info['VRAM']}")
        
        self.whisper_model_combobox.bind("<<ComboboxSelected>>", update_resource_info)
        
        # Options de performance
        perf_frame = tk.Frame(advanced_card, bg=COLORS["card_bg"])
        perf_frame.pack(fill="x")
        
        tk.Label(
            perf_frame, 
            text="Performance", 
            font=("Segoe UI", 12), 
            bg=COLORS["card_bg"], 
            fg=COLORS["primary"]
        ).pack(anchor="w", pady=(0, 5))
        
        # Option multi-thread
        self.use_threading = tk.BooleanVar(value=True)
        thread_check = ttk.Checkbutton(
            perf_frame, 
            text="Activer le multi-thread (plus rapide mais consomme plus de ressources)", 
            variable=self.use_threading,
            command=self._update_processor,
            style="TCheckbutton"
        )
        thread_check.pack(anchor="w", pady=5)
        
        # --- SECTION STATUT ET LOG ---
        status_card = ModernFrame(right_column)
        status_card.pack(fill="both", expand=True)
        
        tk.Label(
            status_card, 
            text="État et Log", 
            font=("Segoe UI", 14, "bold"), 
            bg=COLORS["card_bg"]
        ).pack(anchor="w", pady=(0, 15))
        
        # Zone d'état du système
        system_frame = tk.Frame(status_card, bg=COLORS["card_bg"])
        system_frame.pack(fill="x", pady=(0, 15))
        
        # État GPU avec icône
        gpu_status_frame = tk.Frame(system_frame, bg=COLORS["card_bg"])
        gpu_status_frame.pack(fill="x", pady=5)
        
        gpu_icon_color = COLORS["success"] if config.is_cuda_available() else COLORS["error"]
        gpu_icon = tk.Canvas(gpu_status_frame, width=12, height=12, bg=COLORS["card_bg"], highlightthickness=0)
        gpu_icon.create_oval(2, 2, 10, 10, fill=gpu_icon_color, outline="")
        gpu_icon.pack(side="left", padx=(0, 5))
        
        gpu_text = "GPU disponible: " + (config.get_gpu_name() if config.is_cuda_available() else "Non disponible")
        gpu_status = tk.Label(
            gpu_status_frame, 
            text=gpu_text, 
            bg=COLORS["card_bg"], 
            font=self.default_font
        )
        gpu_status.pack(side="left")
        
        # Fenêtre de log
        log_label = tk.Label(
            status_card, 
            text="Derniers logs:", 
            bg=COLORS["card_bg"], 
            font=self.default_font
        )
        log_label.pack(anchor="w")
        
        log_frame = tk.Frame(status_card, bg=COLORS["card_bg"], bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, pady=(5, 0))
        
        self.log_text = tk.Text(
            log_frame, 
            font=("Consolas", 9), 
            bg="#f8f9fa", 
            height=10,
            wrap="word",
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)
        
        # Scrollbar pour le log
        log_scrollbar = ttk.Scrollbar(self.log_text, orient="vertical", command=self.log_text.yview)
        log_scrollbar.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
        # Configurer le handler de logging pour afficher dans la UI
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                
            def emit(self, record):
                msg = self.format(record)
                
                def append():
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert('end', msg + '\n')
                    self.text_widget.see('end')
                    self.text_widget.configure(state='disabled')
                
                # Schedule to be run in the main thread
                self.text_widget.after(0, append)
        
        # Ajouter le handler personnalisé
        text_handler = TextHandler(self.log_text)
        formatter = logging.Formatter('[%(levelname)s] %(message)s')
        text_handler.setFormatter(formatter)
        
        # Ajouter l'handler au logger
        logger = logging.getLogger()
        logger.addHandler(text_handler)
        
        # --- BOUTON D'ACTION ---
        action_frame = tk.Frame(main_container, bg=COLORS["background"])
        action_frame.pack(fill="x", pady=(20, 0))
        
        process_btn = ModernButton(
            action_frame, 
            text="Démarrer le Traitement", 
            command=lambda: self._process_video(),
            font=("Segoe UI", 12, "bold"),
            padx=20, 
            pady=12,
            bg=COLORS["secondary"],
            hover_color="#ff5a92"
        )
        process_btn.pack()
        
        self._create_menu()
        self._load_defaults()
        
        # Message initial
        logging.info("Application SRT Translator Pro démarrée et prête à l'emploi")
        
        # Appeler la mise à jour des ressources
        update_resource_info(None)

    def _create_menu(self):
        """Crée le menu de l'application."""
        menubar = tk.Menu(self.root)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Sélectionner un fichier vidéo", command=self._select_local_file)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.root.quit)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        
        # Menu Logs
        logs_menu = tk.Menu(menubar, tearoff=0)
        logs_menu.add_command(label="Ouvrir le fichier journal", command=lambda: open_file(os.path.join('logs', 'app.log')))
        logs_menu.add_command(label="Effacer les journaux", command=clear_log_file)
        menubar.add_cascade(label="Journaux", menu=logs_menu)
        
        # Menu Settings
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_checkbutton(label="Utiliser le multi-threading", variable=self.use_threading, command=self._update_processor)
        menubar.add_cascade(label="Paramètres", menu=settings_menu)
        
        # Menu Aide
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="À propos", command=self._show_about)
        help_menu.add_command(label="Aide", command=self._show_help)
        menubar.add_cascade(label="Aide", menu=help_menu)
        
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
        if not self.whisper_model_combobox.get():
            self.whisper_model_combobox.set(config.whisper_model)
    
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
        
        # Modifier cette ligne pour utiliser la méthode correcte de votre ProgressWindow
        # Au lieu de update_status, utilisez la méthode qui existe réellement
        # Par exemple, si vous avez une méthode update_progress:
        # self.progress_window.update_progress("Initialisation...", 0)
        # 
        # Si vous n'avez pas de méthode pour mettre à jour le statut, supprimez cette ligne:
        # self.progress_window.update_status("Initialisation...")
        
        # Démarrer le traitement
        if video_path:
            logging.info(f"Traitement d'un fichier vidéo local: {os.path.basename(video_path)}")
            self.processor.process_video(None, video_path, target_language, translation_service, use_gpu)
        else:
            logging.info(f"Traitement d'une vidéo à partir de l'URL: {url}")
            self.processor.process_video(url, None, target_language, translation_service, use_gpu)

    
    def _select_local_file(self):
        """Sélectionne un fichier vidéo local à traiter."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Fichiers vidéo", "*.mp4 *.mkv *.avi *.mov *.webm")],
            title="Sélectionner une vidéo"
        )
        if file_path:
            # Mettre le chemin dans l'interface
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, "Fichier local: " + os.path.basename(file_path))
            logging.info(f"Fichier vidéo sélectionné: {file_path}")
            
            # Traiter la vidéo
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
            messagebox.showinfo(
                "Traitement annulé", 
                "Le traitement a été annulé par l'utilisateur.",
                icon="info"
            )
        except Exception as e:
            logging.error(f"Erreur lors de l'annulation: {e}")
    
    def _handle_processing_error(self, error_message):
        """Gère une erreur de traitement."""
        try:
            self.progress_window.close()
            messagebox.showerror(
                "Erreur de traitement", 
                f"Une erreur s'est produite lors du traitement :\n\n{error_message}",
                icon="error"
            )
        except Exception as e:
            logging.error(f"Erreur lors de l'affichage de l'erreur: {e}")
    
    def _show_about(self):
        """Affiche la boîte de dialogue À propos avec style moderne."""
        about_window = tk.Toplevel(self.root)
        about_window.title("À propos de SRT Translator Pro")
        about_window.geometry("500x400")
        about_window.resizable(False, False)
        about_window.configure(bg=COLORS["card_bg"])
        
        # Centrer la fenêtre
        about_window.update_idletasks()
        width = about_window.winfo_width()
        height = about_window.winfo_height()
        x = (about_window.winfo_screenwidth() // 2) - (width // 2)
        y = (about_window.winfo_screenheight() // 2) - (height // 2)
        about_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Contenu avec padding
        content_frame = tk.Frame(about_window, bg=COLORS["card_bg"], padx=25, pady=25)
        content_frame.pack(fill="both", expand=True)
        
        try:
            # Logo placeholder - remplacez par votre propre logo
            logo_img = Image.open("assets/logo.png").resize((80, 80))
            logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = tk.Label(content_frame, image=logo_photo, bg=COLORS["card_bg"])
            logo_label.image = logo_photo
            logo_label.pack(pady=(0, 20))
        except:
            # Fallback si pas de logo
            logo_frame = tk.Frame(content_frame, width=80, height=80, bg=COLORS["primary"])
            logo_frame.pack(pady=(0, 20))
        
        # Titre et version
        tk.Label(
            content_frame, 
            text="SRT Translator Pro", 
            font=("Segoe UI", 18, "bold"), 
            bg=COLORS["card_bg"], 
            fg=COLORS["primary"]
        ).pack()
        
        tk.Label(
            content_frame, 
            text="Version 1.1", 
            font=("Segoe UI", 10), 
            bg=COLORS["card_bg"], 
            fg=COLORS["text_secondary"]
        ).pack(pady=(0, 20))
        
        # Description
        description = """Une application avancée pour télécharger des vidéos, extraire l'audio, transcrire et traduire les sous-titres en utilisant la puissance de l'IA.

Fonctionnalités :
• Téléchargement de vidéos depuis diverses plateformes
• Extraction et traitement audio intelligent
• Transcription automatique avec Whisper
• Traduction avec DeepL et OpenAI
• Optimisation multi-thread pour des performances accrues

Développée avec Python et tkinter."""

        text_box = tk.Text(
            content_frame, 
            font=("Segoe UI", 10), 
            bg=COLORS["card_bg"],
            relief="flat",
            height=10,
            wrap="word"
        )
        text_box.insert("1.0", description)
        text_box.config(state="disabled")
        text_box.pack(fill="both", expand=True)
        
        # Bouton OK pour fermer
        ok_button = ModernButton(
            content_frame, 
            text="Fermer", 
            command=about_window.destroy,
            bg=COLORS["primary"],
            padx=20,
            pady=5,
            font=("Segoe UI", 10)
        )
        ok_button.pack(pady=(20, 0))
    
    def _show_help(self):
        """Affiche l'aide de l'application avec style moderne."""
        help_window = tk.Toplevel(self.root)
        help_window.title("Aide - SRT Translator Pro")
        help_window.geometry("600x500")
        help_window.configure(bg=COLORS["card_bg"])
        
        # Centrer la fenêtre
        help_window.update_idletasks()
        width = help_window.winfo_width()
        height = help_window.winfo_height()
        x = (help_window.winfo_screenwidth() // 2) - (width // 2)
        y = (help_window.winfo_screenheight() // 2) - (height // 2)
        help_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # Panneau principal
        main_frame = tk.Frame(help_window, bg=COLORS["card_bg"], padx=25, pady=25)
        main_frame.pack(fill="both", expand=True)
        
        # En-tête
        tk.Label(
            main_frame, 
            text="Guide d'utilisation", 
            font=("Segoe UI", 16, "bold"), 
            bg=COLORS["card_bg"], 
            fg=COLORS["primary"]
        ).pack(anchor="w", pady=(0, 20))
        
        # Zone d'onglets
        tab_control = ttk.Notebook(main_frame)
        
        # Onglet Démarrage rapide
        quick_start = ttk.Frame(tab_control)
        tab_control.add(quick_start, text="Démarrage rapide")
        
        quick_start_frame = tk.Frame(quick_start, bg=COLORS["card_bg"], padx=15, pady=15)
        quick_start_frame.pack(fill="both", expand=True)
        
        quick_guide = """Comment utiliser SRT Translator Pro:

1. Entrez une URL de vidéo dans le champ ou sélectionnez un fichier local avec le bouton "Parcourir".

2. Configurez les clés API pour DeepL et/ou OpenAI selon le service de traduction que vous souhaitez utiliser.

3. Sélectionnez la langue cible et le service de traduction.

4. Ajustez les paramètres avancés si nécessaire (modèle Whisper, utilisation du GPU, etc.).

5. Cliquez sur "Démarrer le traitement".

6. Suivez la progression dans la fenêtre qui apparaît. Vous pouvez annuler à tout moment si nécessaire."""
        
        qs_text = tk.Text(
            quick_start_frame, 
            bg=COLORS["card_bg"],
            relief="flat",
            wrap="word", 
            font=("Segoe UI", 10),
            height=15
        )
        qs_text.insert("1.0", quick_guide)
        qs_text.config(state="disabled")
        qs_text.pack(fill="both", expand=True)
        
        # Onglet Paramètres avancés
        adv_tab = ttk.Frame(tab_control)
        tab_control.add(adv_tab, text="Paramètres avancés")
        
        adv_frame = tk.Frame(adv_tab, bg=COLORS["card_bg"], padx=15, pady=15)
        adv_frame.pack(fill="both", expand=True)
        
        adv_guide = """Paramètres avancés:

• Modèles Whisper:
  - tiny: Rapide, moins précis, idéal pour les tests (faibles ressources)
  - base: Bon équilibre vitesse/précision pour les contenus simples
  - small: Précision améliorée, adapté à la plupart des contenus
  - medium: Haute précision, recommandé pour les contenus complexes
  - large: Précision maximale, idéal pour les contenus difficiles
  - large-v3-turbo: Dernière version, plus rapide et plus précise

• Utilisation GPU:
  L'option GPU accélère considérablement le traitement mais nécessite une carte NVIDIA compatible CUDA. La quantité de VRAM nécessaire dépend du modèle Whisper choisi.

• Multi-threading:
  Permet de traiter plusieurs tâches simultanément, ce qui accélère le processus global. Désactivez cette option si vous rencontrez des problèmes de stabilité ou de ressources."""
        
        adv_text = tk.Text(
            adv_frame, 
            bg=COLORS["card_bg"],
            relief="flat",
            wrap="word", 
            font=("Segoe UI", 10),
            height=15
        )
        adv_text.insert("1.0", adv_guide)
        adv_text.config(state="disabled")
        adv_text.pack(fill="both", expand=True)
        
        # Onglet Dépannage
        troubleshoot_tab = ttk.Frame(tab_control)
        tab_control.add(troubleshoot_tab, text="Dépannage")
        
        trouble_frame = tk.Frame(troubleshoot_tab, bg=COLORS["card_bg"], padx=15, pady=15)
        trouble_frame.pack(fill="both", expand=True)
        
        trouble_guide = """Résolution des problèmes courants:

• Erreur d'API: 
  Vérifiez que vos clés API sont correctes et que vous avez suffisamment de crédits.

• Erreur de téléchargement:
  Assurez-vous que l'URL est valide et accessible. Certaines plateformes peuvent restreindre les téléchargements.

• Erreur de mémoire:
  Essayez un modèle Whisper plus petit ou désactivez le multi-threading.

• Erreur GPU:
  Si vous rencontrez des problèmes avec le GPU, désactivez-le et utilisez le CPU.

• Traduction incomplète:
  Pour les vidéos longues, certains services peuvent limiter la taille des entrées. Essayez de diviser le traitement en sections plus petites.

Pour plus d'aide, consultez les journaux d'application dans le menu "Journaux" > "Ouvrir le fichier journal"."""
        
        trouble_text = tk.Text(
            trouble_frame, 
            bg=COLORS["card_bg"],
            relief="flat",
            wrap="word", 
            font=("Segoe UI", 10),
            height=15
        )
        trouble_text.insert("1.0", trouble_guide)
        trouble_text.config(state="disabled")
        trouble_text.pack(fill="both", expand=True)
        
        # Fin des onglets
        tab_control.pack(fill="both", expand=True)
        
        # Liens externes (optionnel)
        links_frame = tk.Frame(main_frame, bg=COLORS["card_bg"], pady=10)
        links_frame.pack(fill="x")
        
        def open_link(url):
            webbrowser.open_new_tab(url)
        
        docs_link = tk.Label(
            links_frame, 
            text="Documentation en ligne",
            fg=COLORS["primary"],
            bg=COLORS["card_bg"],
            cursor="hand2",
            font=("Segoe UI", 9, "underline")
        )
        docs_link.pack(side="left", padx=(0, 15))
        docs_link.bind("<Button-1>", lambda e: open_link("https://huggingface.co/docs"))
        
        api_link = tk.Label(
            links_frame, 
            text="API DeepL",
            fg=COLORS["primary"],
            bg=COLORS["card_bg"],
            cursor="hand2",
            font=("Segoe UI", 9, "underline")
        )
        api_link.pack(side="left", padx=(0, 15))
        api_link.bind("<Button-1>", lambda e: open_link("https://www.deepl.com/docs-api"))
        
        # Bouton fermer
        close_button = ModernButton(
            main_frame, 
            text="Fermer", 
            command=help_window.destroy,
            bg=COLORS["primary"],
            font=("Segoe UI", 10),
            padx=20,
            pady=5
        )
        close_button.pack(pady=(15, 0))
    
    def run(self):
        """Lance l'application."""
        # Journaliser le démarrage de l'application
        logging.info("=== Application SRT Translator Pro démarrée (avec support multi-thread) ===")
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
