from huggingface_hub import hf_hub_download
from utils import progress_queue
import logging
import os

def download_whisper_model(model_name):
    """Télécharge un modèle Whisper avec barre de progression améliorée."""
    try:
        # Extraire le nom de base du modèle (sans 'openai/whisper-')
        base_name = model_name.replace("openai/whisper-", "")
        
        # Mettre à jour l'interface utilisateur
        progress_queue.put({"value": 15, "status_text": f"Téléchargement du modèle Whisper {base_name}..."})
        
        # Désactiver temporairement les logs de huggingface
        logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
        
        # Fonction de callback pour la progression
        def download_progress_callback(progress):
            # Mettre à jour la barre de progression plus fréquemment (tous les 5%)
            if progress.total:
                update_step = max(1, progress.total // 20)  # 5% de progression
                if progress.completed % update_step == 0 or progress.completed == progress.total:
                    percent = min(100, int(progress.completed * 100 / progress.total))
                    # Convertir les tailles en formats lisibles
                    completed_mb = progress.completed / (1024 * 1024)
                    total_mb = progress.total / (1024 * 1024)
                    
                    progress_queue.put({
                        "value": 15 + min(20, int(percent / 5)),  # Partage de la progression entre 15% et 35%
                        "status_text": f"Téléchargement du modèle Whisper {base_name}: {percent}% ({completed_mb:.1f}MB / {total_mb:.1f}MB)"
                    })
        
        # Télécharger le modèle avec suivi de progression
        model_path = hf_hub_download(
            repo_id=f"openai/whisper-{base_name}",
            filename="model.safetensors",
            cache_dir=os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"),
            force_download=False,
            resume_download=True,
            proxies=None,
            local_files_only=False,
            token=None,
            progress_callback=download_progress_callback
        )
        
        # Mise à jour finale de la progression
        progress_queue.put({
            "value": 35, 
            "status_text": f"Modèle Whisper {base_name} téléchargé avec succès!"
        })
        
        return model_path
    except Exception as e:
        logging.error(f"Erreur lors du téléchargement du modèle: {str(e)}")
        progress_queue.put({"value": 20, "status_text": f"Chargement du modèle Whisper {base_name} depuis le cache..."})
        # Continuer avec le flux normal en cas d'erreur
        return None