#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module pour les composants d'interface utilisateur.
"""

import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
from tkinter import ttk
import logging
import threading
import queue

from utils import log_queue, progress_queue, command_queue, open_folder

class ProgressWindow:
    """Fenêtre affichant la progression du traitement avec logs."""
    
    def __init__(self, parent, title="Traitement en cours"):
        """
        Initialise la fenêtre de progression.
        
        Args:
            parent: Fenêtre parente
            title: Titre de la fenêtre
        """
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("1000x700")  # Fenêtre plus grande pour les logs
        self.window.resizable(True, True)
        
        # Rendre la fenêtre modale
        self.window.transient(parent)
        self.window.grab_set()
        
        # Configurer le style
        self.window.configure(bg="#ffffff")
        
        # Centrer la fenêtre
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        x = parent_x + (parent_width // 2) - 375
        y = parent_y + (parent_height // 2) - 275
        
        self.window.geometry(f"+{x}+{y}")
        
        # Frame pour la partie supérieure
        top_frame = tk.Frame(self.window, bg="#ffffff")
        top_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        # Label pour le statut
        self.status_label = tk.Label(top_frame, text="Initialisation...", font=("Helvetica", 10), bg="#ffffff")
        self.status_label.pack(pady=(0, 10))
        
        # Frame pour la barre de progression
        progress_frame = tk.Frame(top_frame, bg="#ffffff")
        progress_frame.pack(fill="x")

        # ✅ Définir d'abord la variable liée à la barre de progression
        self.progress_var = tk.DoubleVar()

        # ✅ Créer la barre de progression avec la variable
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            length=710,
            mode="determinate",
            variable=self.progress_var
        )
        self.progress_bar.pack(fill="x")



        # ✅ Barre de progression liée à la variable
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            length=710,
            mode="determinate",
            variable=self.progress_var
        )
        self.progress_bar.pack(fill="x")

        self.progress_bar.pack(fill="x")
        
        # Label pour le pourcentage
        self.percentage_label = tk.Label(top_frame, text="0%", font=("Helvetica", 9), bg="#ffffff")
        self.percentage_label.pack(pady=5)
        
        # Frame pour les logs
        log_frame = tk.Frame(self.window, bg="#ffffff")
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Label pour les logs
        log_label = tk.Label(log_frame, text="Logs de traitement:", font=("Helvetica", 10, "bold"), bg="#ffffff", anchor="w")
        log_label.pack(fill="x", pady=(0, 5))
        
        # Zone de texte pour les logs
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=90, height=20, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("INFO", foreground="black")
        self.log_text.tag_configure("DEBUG", foreground="blue")
        self.log_text.tag_configure("WARNING", foreground="orange")
        self.log_text.tag_configure("ERROR", foreground="red")
        self.log_text.tag_configure("CRITICAL", foreground="red", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("CONSOLE", foreground="green")
        self.log_text.tag_configure("TRANSCRIPTION", foreground="#800080")
        self.log_text.tag_configure("YTDLP", foreground="#008080")
        
        # Frame pour les boutons
        button_frame = tk.Frame(self.window, bg="#ffffff")
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Bouton d'annulation
        self.cancel_button = tk.Button(button_frame, text="Annuler", command=self.cancel, bg="#f44336", fg="white")
        self.cancel_button.pack(side="left", padx=5)
        
        # Bouton pour effacer les logs
        self.clear_logs_button = tk.Button(button_frame, text="Effacer les logs", command=self._clear_logs, bg="#607d8b", fg="white")
        self.clear_logs_button.pack(side="left", padx=5)
        
        # Bouton pour sauvegarder les logs
        self.save_logs_button = tk.Button(button_frame, text="Sauvegarder les logs", command=self._save_logs, bg="#2196F3", fg="white")
        self.save_logs_button.pack(side="left", padx=5)
        
        # Variable pour suivre si le processus a été annulé
        self.cancelled = False
        
        # Empêcher la fermeture avec le bouton X
        self.window.protocol("WM_DELETE_WINDOW", self._disable_close)
        
        # Démarrer les threads de mise à jour
        self.running = True
        
        # Thread pour les logs
        self.log_thread = threading.Thread(target=self._process_log_queue)
        self.log_thread.daemon = True
        self.log_thread.start()
        
        # Thread pour les mises à jour de progression
        self.progress_thread = threading.Thread(target=self._process_progress_queue)
        self.progress_thread.daemon = True
        self.progress_thread.start()
        
        # Mettre à jour l'interface
        self.window.update()
    
    def _process_log_queue(self):
        """Traite les logs dans la queue et les affiche dans la zone de texte."""
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        while self.running:
            try:
                # Récupérer un log de la queue
                record = log_queue.get(block=True, timeout=0.1)
                
                # Formater le message
                msg = log_formatter.format(record)
                
                # Déterminer le tag en fonction du niveau de log et du contenu
                level_tag = "INFO"
                if record.levelno == logging.DEBUG:
                    level_tag = "DEBUG"
                elif record.levelno == logging.WARNING:
                    level_tag = "WARNING"
                elif record.levelno == logging.ERROR:
                    level_tag = "ERROR"
                elif record.levelno == logging.CRITICAL:
                    level_tag = "CRITICAL"
                
                # Détecter les messages spécifiques
                if "Transcription Results" in record.getMessage() or \
                   "-->" in record.getMessage() or \
                   "Detected language:" in record.getMessage():
                    level_tag = "TRANSCRIPTION"
                
                if "youtube-dl" in record.getMessage() or \
                   "[download]" in record.getMessage() or \
                   "ffmpeg" in record.getMessage():
                    level_tag = "YTDLP"
                
                # Afficher le message dans la zone de texte
                self.window.after(0, self._append_log, msg, level_tag)
                
                # Libérer la queue
                log_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                # En cas d'erreur, ne pas bloquer le thread
                try:
                    self.window.after(0, self._append_error_log, f"Erreur de traitement des logs: {str(e)}")
                except:
                    pass
    
    def _append_log(self, msg, level_tag):
        """Ajoute un message de log à la zone de texte (thread-safe)."""
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, msg + "\n", level_tag)
            self.log_text.see(tk.END)  # Défiler automatiquement vers le bas
            self.log_text.configure(state="disabled")
        except Exception as e:
            print(f"Erreur d'affichage de log: {e}")
    
    def _append_error_log(self, msg):
        """Ajoute un message d'erreur à la zone de texte (thread-safe)."""
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, msg + "\n", "ERROR")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")
        except:
            pass
    
    def _process_progress_queue(self):
        """Traite les mises à jour de progression dans la queue."""
        while self.running:
            try:
                # Récupérer une mise à jour de la queue
                progress_update = progress_queue.get(block=True, timeout=0.1)
                
                # Extraire les valeurs
                value = progress_update.get('value', 0)
                status_text = progress_update.get('status_text', None)
                
                # Mettre à jour l'interface
                self.window.after(0, self.update_progress_ui, value, status_text)
                
                # Libérer la queue
                progress_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                # En cas d'erreur, ne pas bloquer le thread
                print(f"Erreur de mise à jour de progression: {e}")
    
    def update_progress_ui(self, value=None, status_text=None):
        if status_text:
            self.status_label.config(text=status_text)

        if value is not None:
            self.progress_var.set(value)

    def _clear_logs(self):
        """Efface les logs dans la zone de texte."""
        self.log_text.configure(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state="disabled")
    
    def _save_logs(self):
        """Sauvegarde les logs dans un fichier."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                title="Sauvegarder les logs"
            )
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("Logs sauvegardés", f"Les logs ont été sauvegardés dans {file_path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder les logs: {str(e)}")
    
    def cancel(self):
        """Annule le processus en cours."""
        self.cancelled = True
        self.status_label.config(text="Annulation en cours...")
        logging.warning("Annulation demandée par l'utilisateur")
        # Mettre la commande d'annulation dans la queue
        command_queue.put({"command": "cancel"})
        self.window.update()
    
    def is_cancelled(self):
        """Retourne True si l'utilisateur a annulé le processus."""
        return self.cancelled
    
    def _disable_close(self):
        """Empêche la fermeture de la fenêtre avec le bouton X."""
        pass
    
    def close(self):
        """Ferme la fenêtre de progression."""
        try:
            self.running = False
            if self.log_thread.is_alive():
                self.log_thread.join(timeout=1.0)
            if self.progress_thread.is_alive():
                self.progress_thread.join(timeout=1.0)
            self.window.destroy()
        except:
            pass


class ResultDialog:
    """Boîte de dialogue personnalisée pour afficher le résultat du traitement."""
    
    def __init__(self, parent, title, message, folder_path):
        """
        Initialise la boîte de dialogue de résultat.
        
        Args:
            parent: Fenêtre parente
            title: Titre de la boîte de dialogue
            message: Message à afficher
            folder_path: Chemin vers le dossier des résultats
        """
        self.result = None
        self.folder_path = folder_path
        
        # Créer la fenêtre de dialogue
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("700x400")
        self.dialog.resizable(False, False)
        
        # Rendre la fenêtre modale
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Centrer la fenêtre
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        x = parent_x + (parent_width // 2) - 250
        y = parent_y + (parent_height // 2) - 125
        
        self.dialog.geometry(f"+{x}+{y}")
        
        # Configurer l'apparence
        self.dialog.configure(bg="#ffffff")
        
        # Frame principale
        main_frame = tk.Frame(self.dialog, bg="#ffffff", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)
        
        # Icône de succès
        success_label = tk.Label(main_frame, text="✓", font=("Helvetica", 36), fg="#4CAF50", bg="#ffffff")
        success_label.pack(pady=(0, 10))
        
        # Message
        msg_label = tk.Label(main_frame, text=message, wraplength=460, 
                            justify="center", bg="#ffffff", font=("Helvetica", 10))
        msg_label.pack(pady=(0, 20))
        
        # Frame pour le chemin du dossier
        path_frame = tk.Frame(main_frame, bg="#f0f0f0", padx=10, pady=10)
        path_frame.pack(fill="x", pady=(0, 20))
        
        # Afficher le chemin du dossier
        path_label = tk.Label(path_frame, text=folder_path, bg="#f0f0f0", 
                              font=("Consolas", 9), wraplength=460)
        path_label.pack()
        
        # Frame pour les boutons
        button_frame = tk.Frame(main_frame, bg="#ffffff")
        button_frame.pack()
        
        # Bouton pour ouvrir le dossier
        open_button = tk.Button(button_frame, text="Ouvrir le dossier", 
                              command=self._open_folder, bg="#2196F3", fg="white",
                              font=("Helvetica", 10, "bold"), padx=15, pady=5)
        open_button.pack(side="left", padx=5)
        
        # Bouton OK 
        ok_button = tk.Button(button_frame, text="OK", 
                            command=self._ok, bg="#4CAF50", fg="white",
                            font=("Helvetica", 10, "bold"), padx=15, pady=5)
        ok_button.pack(side="left", padx=5)
    
    def _open_folder(self):
        """Ouvre le dossier des résultats."""
        open_folder(self.folder_path)
    
    def _ok(self):
        """Ferme la boîte de dialogue."""
        self.dialog.destroy()
    
    def show(self):
        """Affiche la boîte de dialogue et attend que l'utilisateur réponde."""
        self.dialog.wait_window()
        return self.result
