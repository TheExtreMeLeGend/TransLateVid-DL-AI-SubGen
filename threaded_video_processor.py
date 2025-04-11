#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module coordinateur du traitement des vidéos avec support multi-thread.
"""

import os
import logging
import shutil
import threading
import concurrent.futures
from openai import OpenAI
import time
import queue

from utils import progress_queue, command_queue, restore_std_redirects, enable_std_redirects
from video_downloader import download_video, sanitize_filename, ensure_unique_path
from audio_extractor import extract_audio, separate_audio
from transcriber import transcribe_audio
from translate import translate_srt_file, set_api_keys
from utils import progress_queue, command_queue, restore_std_redirects, enable_std_redirects, format_whisper_model_name

class ThreadedVideoProcessor:
    """Classe gérant le workflow complet de traitement des vidéos avec support multi-thread."""
    
    def __init__(self, config):
        """
        Initialise le processeur de vidéos.
        
        Args:
            config: Instance de la configuration
        """
        self.config = config
        self.cancelled = False
        self.client = None
        self.update_api_client()
        
        # Nombre de workers pour le pool de threads
        self.max_workers = os.cpu_count() or 4
        # Limite le nombre à un maximum raisonnable
        self.max_workers = min(self.max_workers, 8)
        logging.info(f"Initialisation du ThreadedVideoProcessor avec {self.max_workers} workers")
        
        # Verrou pour éviter les conflits d'accès
        self.lock = threading.Lock()
    
    def update_api_client(self):
        """Met à jour le client OpenAI avec la clé de l'utilisateur."""
        self.client = OpenAI(api_key=self.config.openai_key)
        # Mettre à jour aussi dans le module translate
        set_api_keys(self.config.deepl_key, self.config.openai_key)
    
    def process_video(self, url=None, video_path=None, target_language=None, translation_service=None, use_gpu=None):
        """
        Traite une vidéo à partir d'une URL ou d'un fichier local.
        
        Args:
            url: URL de la vidéo à télécharger (facultatif)
            video_path: Chemin vers un fichier vidéo local (facultatif)
            target_language: Langue cible pour la traduction
            translation_service: Service de traduction à utiliser ('DeepL' ou 'ChatGPT')
            use_gpu: Indique s'il faut utiliser le GPU pour le traitement
            
        Returns:
            True si le traitement s'est terminé avec succès, False sinon
        """
        # Vérifier les entrées
        if not url and not video_path:
            logging.error("Aucune URL ni fichier vidéo spécifié")
            command_queue.put({"command": "error", "message": "Veuillez entrer une URL ou sélectionner un fichier vidéo."})
            return False
        
        if not target_language:
            target_language = self.config.default_language.split(' - ')[0]
        
        if not translation_service:
            translation_service = self.config.default_service
        
        if use_gpu is None:
            use_gpu = self.config.use_gpu
        
        # Démarrer le processus dans un thread séparé
        processing_thread = threading.Thread(
            target=self._process_video_thread,
            args=(url, video_path, target_language, translation_service, use_gpu)
        )
        processing_thread.daemon = True
        processing_thread.start()
        
        return True
    
    def _update_progress(self, value, status_text):
        """Met à jour la progression en thread-safe."""
        with self.lock:
            progress_queue.put({"value": value, "status_text": status_text})
    
    def _check_cancelled(self):
        """Vérifie si l'utilisateur a annulé le traitement."""
        try:
            # Vérifier s'il y a une commande d'annulation dans la queue
            cmd = command_queue.get_nowait()
            if cmd.get("command") == "cancel":
                logging.info("Traitement annulé par l'utilisateur")
                command_queue.put({"command": "processing_cancelled"})
                return True
            else:
                # Remettre la commande dans la queue si ce n'est pas une annulation
                command_queue.put(cmd)
        except queue.Empty:
            # Pas de commande dans la queue
            pass
            
        # Vérifier également le flag interne
        if self.cancelled:
            logging.info("Traitement annulé (flag interne)")
            command_queue.put({"command": "processing_cancelled"})
            return True
            
        return False
    
    def _download_or_use_local_video(self, url, video_path, output_folder):
        """Télécharge ou utilise un fichier vidéo local."""
        if video_path:
            video_title = sanitize_filename(os.path.splitext(os.path.basename(video_path))[0])
            self._update_progress(10, f"Utilisation du fichier local: {video_title}")
            return video_path, video_title
        else:
            self._update_progress(10, "Téléchargement de la vidéo...")
            
            # Télécharger la vidéo
            downloaded_video_path, video_title = download_video(url, output_folder)
            
            if self._check_cancelled():
                return None, None
                
            if not video_title:
                raise FileNotFoundError(f"Le téléchargement de la vidéo a échoué pour {url}")

            video_title = sanitize_filename(video_title)
            video_folder = os.path.join(output_folder, video_title)
            if not os.path.exists(video_folder):
                os.makedirs(video_folder)
            
            video_path = os.path.join(video_folder, f"{video_title}.mp4")
            
            # Assurer un nom de fichier unique
            if os.path.exists(video_path):
                video_path = ensure_unique_path(video_path)
            
            self._update_progress(20, "Finalisation du téléchargement...")
            os.rename(downloaded_video_path, video_path)
            
            return video_path, video_title
    
    def _extract_audio_task(self, video_path, audio_path):
        """Tâche d'extraction audio exécutée dans un thread."""
        self._update_progress(30, "Extraction de l'audio...")
        extract_audio(video_path, audio_path)
        return audio_path
    
    def _separate_audio_task(self, audio_path, separated_folder, use_gpu):
        """Tâche de séparation audio exécutée dans un thread."""
        self._update_progress(40, "Séparation des pistes audio...")
        separate_audio(audio_path, separated_folder, use_gpu=use_gpu)
        
        vocal_path = os.path.join(separated_folder, 'vocals.wav')
        accompaniment_path = os.path.join(separated_folder, 'accompaniment.wav')
        
        if not os.path.exists(vocal_path):
            raise FileNotFoundError(f"Piste vocale non trouvée à {vocal_path}.")
        if not os.path.exists(accompaniment_path):
            raise FileNotFoundError(f"Piste d'accompagnement non trouvée à {accompaniment_path}.")
            
        return vocal_path, accompaniment_path
    
    def _transcribe_audio_task(self, audio_path, transcript_path, is_vocal, use_gpu):
        """Tâche de transcription exécutée dans un thread."""
        if is_vocal:
            self._update_progress(70, "Transcription de la piste vocale...")
        else:
            self._update_progress(55, "Transcription de l'audio principal...")
        
        # Ajouter des logs pour débugging
        model_name = format_whisper_model_name(self.config.whisper_model)
        logging.info(f"ℹ️ DEBUG: Modèle dans config: {self.config.whisper_model}")
        logging.info(f"ℹ️ DEBUG: Modèle après formatage: {model_name}")
        
        transcribe_audio(audio_path, transcript_path, model_name=model_name, use_gpu=use_gpu)
        return f"{transcript_path}.srt"
    
    def _translate_srt_task(self, srt_path, target_language, translation_service, is_vocal):
        """Tâche de traduction exécutée dans un thread."""
        if is_vocal:
            self._update_progress(90, f"Traduction de la transcription vocale en {target_language}...")
        else:
            self._update_progress(80, f"Traduction de la transcription principale en {target_language}...")
            
        translated_path, translated_content = translate_srt_file(
            srt_path, 
            target_language, 
            translation_service
        )
        
        return translated_path, translated_content
    
    def _process_video_thread(self, url, video_path, target_language, translation_service, use_gpu):
        """Fonction exécutée dans un thread séparé pour traiter la vidéo avec parallélisation."""
        try:
            # Désactiver temporairement la redirection pour yt-dlp
            restore_std_redirects()
            
            # Log des paramètres
            logging.info("=== Début du traitement de la vidéo (mode multi-thread) ===")
            if video_path:
                logging.info(f"Fichier vidéo local: {video_path}")
            else:
                logging.info(f"URL: {url}")
            logging.info(f"Langue cible: {target_language}")
            logging.info(f"Service de traduction: {translation_service}")
            logging.info(f"Utilisation du GPU: {'Oui' if use_gpu else 'Non'}")
            logging.info(f"Nombre de workers: {self.max_workers}")
            
            output_folder = self.config.output_folder
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            
            # Étape 1: Traitement de la vidéo (10%)
            self._update_progress(5, "Préparation de la vidéo...")
            
            # Télécharger ou utiliser le fichier local
            video_path, video_title = self._download_or_use_local_video(url, video_path, output_folder)
            
            if self._check_cancelled() or not video_path:
                enable_std_redirects()  # Restaurer la redirection
                return
            
            if not os.path.exists(video_path):
                enable_std_redirects()  # Restaurer la redirection
                raise FileNotFoundError(f"Vidéo non trouvée à {video_path}")

            # Restaurer la redirection pour la suite
            enable_std_redirects()
                
            # Étape 2: Préparation des dossiers (25%)
            self._update_progress(25, "Préparation des dossiers...")
            
            video_folder = os.path.join(output_folder, video_title)
            if not os.path.exists(video_folder):
                os.makedirs(video_folder)

            destination_video_path = os.path.join(video_folder, os.path.basename(video_path))
            
            # Assurer un nom unique pour le fichier copié
            if os.path.exists(destination_video_path) and destination_video_path != video_path:
                destination_video_path = ensure_unique_path(destination_video_path)
                shutil.copy(video_path, destination_video_path)
                video_path = destination_video_path

            audio_path = os.path.join(video_folder, f"{video_title}.mp3")
            transcript_path = os.path.join(video_folder, video_title)
            vocal_transcript_path = os.path.join(video_folder, f"{video_title}_vocal")
            separated_folder = os.path.join(video_folder, "separated")

            if not os.path.exists(separated_folder):
                os.makedirs(separated_folder)

            logging.info(f"Chemin de la vidéo : {video_path}")
            logging.info(f"Chemin de l'audio : {audio_path}")
            logging.info(f"Chemin de la transcription : {transcript_path}")
            logging.info(f"Chemin de la transcription vocale : {vocal_transcript_path}")
            logging.info(f"Chemin des fichiers séparés : {separated_folder}")

            if self._check_cancelled():
                return

            # Utiliser un ThreadPoolExecutor pour paralléliser les tâches
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Étape 3: Extraction audio (exécutée séquentiellement car nécessaire avant la séparation)
                future_extract = executor.submit(
                    self._extract_audio_task, 
                    video_path, 
                    audio_path
                )
                
                try:
                    # Attendre l'extraction audio
                    audio_path = future_extract.result()
                    
                    if self._check_cancelled():
                        return
                    
                    if not os.path.exists(audio_path):
                        raise FileNotFoundError(f"Audio non trouvé à {audio_path}")
                    
                    # Soumettre les tâches en parallèle
                    # 1. Séparation audio
                    future_separate = executor.submit(
                        self._separate_audio_task,
                        audio_path,
                        separated_folder,
                        use_gpu
                    )
                    
                    # 2. Transcription de l'audio principal
                    future_transcribe_main = executor.submit(
                        self._transcribe_audio_task,
                        audio_path,
                        transcript_path,
                        False,
                        use_gpu
                    )
                    
                    # Attendre la séparation audio
                    vocal_path, _ = future_separate.result()
                    
                    if self._check_cancelled():
                        return
                    
                    # 3. Transcription de la piste vocale (démarre après séparation)
                    future_transcribe_vocal = executor.submit(
                        self._transcribe_audio_task,
                        vocal_path,
                        vocal_transcript_path,
                        True,
                        use_gpu
                    )
                    
                    # Attendre la transcription principale
                    main_srt_path = future_transcribe_main.result()
                    
                    if self._check_cancelled():
                        return
                    
                    # 4. Traduction de la transcription principale
                    future_translate_main = executor.submit(
                        self._translate_srt_task,
                        main_srt_path,
                        target_language,
                        translation_service,
                        False
                    )
                    
                    # Attendre la transcription vocale
                    vocal_srt_path = future_transcribe_vocal.result()
                    
                    if self._check_cancelled():
                        return
                    
                    # 5. Traduction de la transcription vocale
                    future_translate_vocal = executor.submit(
                        self._translate_srt_task,
                        vocal_srt_path,
                        target_language,
                        translation_service,
                        True
                    )
                    
                    # Attendre les traductions et enregistrer les résultats
                    _, main_translated_content = future_translate_main.result()
                    
                    final_translated_path = os.path.join(video_folder, f"{target_language}_{video_title}_{target_language}.srt")
                    with open(final_translated_path, 'w', encoding='utf-8') as f:
                        f.write(main_translated_content)
                    
                    logging.info(f"Transcription traduite enregistrée: {final_translated_path}")
                    
                    if self._check_cancelled():
                        return
                    
                    # Sauvegarder la traduction vocale
                    _, vocal_translated_content = future_translate_vocal.result()
                    
                    final_vocal_translated_path = os.path.join(video_folder, f"{target_language}_{video_title}_vocal_{target_language}.srt")
                    with open(final_vocal_translated_path, 'w', encoding='utf-8') as f:
                        f.write(vocal_translated_content)
                    
                    logging.info(f"Transcription vocale traduite enregistrée: {final_vocal_translated_path}")
                    
                except concurrent.futures.CancelledError:
                    logging.warning("Une ou plusieurs tâches ont été annulées")
                    return
                    
            # Finalisation (100%)
            self._update_progress(100, "Traitement terminé avec succès!")
            logging.info("=== Traitement terminé avec succès (mode multi-thread) ===")
            
            # Signal de fin de traitement
            command_queue.put({"command": "processing_done", "video_folder": video_folder})
            
        except Exception as e:
            logging.error(f"Erreur: {str(e)}", exc_info=True)
            # Signal d'erreur
            command_queue.put({"command": "error", "message": str(e)})
        finally:
            # S'assurer que la redirection est restaurée
            enable_std_redirects()
    
    def cancel_processing(self):
        """Annule le traitement en cours."""
        self.cancelled = True
        logging.warning("Annulation demandée par l'utilisateur")
        command_queue.put({"command": "cancel"})
