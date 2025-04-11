import yt_dlp
import os
import re
import unicodedata
import logging
import emoji
from pathlib import Path
import shutil
import tempfile
import hashlib
import time
import io

# Module de logging configuré
logger = logging.getLogger(__name__)

# Classe personnalisée pour capturer la sortie de yt-dlp
class YTDLPLogger:
    def debug(self, msg):
        if msg.startswith('[download]'):
            logger.info(msg)
        else:
            logger.debug(msg)
            
    def info(self, msg):
        logger.info(msg)
        
    def warning(self, msg):
        logger.warning(msg)
        
    def error(self, msg):
        logger.error(msg)

MAX_FILENAME_LENGTH = 50

def remove_emojis(text):
    """Remove all emojis from the text."""
    if not text:
        return ""
    return emoji.replace_emoji(text, replace='')

def sanitize_filename(filename):
    """Sanitize the filename by replacing invalid characters for Windows and limit its length."""
    if not filename:
        return "unknown_video"
    
    # Normalisation cohérente pour les caractères non-latins (comme l'arabe)
    filename = unicodedata.normalize('NFKC', filename)
    filename = remove_emojis(filename)
    
    # Supprimer les caractères interdits pour les noms de fichiers
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    filename = filename.strip().rstrip('.')
    
    # Limiter la longueur du nom de fichier
    if len(filename) > MAX_FILENAME_LENGTH:
        filename = filename[:MAX_FILENAME_LENGTH]
    
    logger.info(f"Nom de fichier sanitisé: {filename}")
    return filename

# Fonction ensure_unique_path réintégrée pour maintenir la compatibilité
def ensure_unique_path(path):
    """Ensure the file path is unique."""
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(path):
        new_path = f"{base} ({counter}){ext}"
        path = new_path
        counter += 1
    return path

def convert_to_ascii(filename, max_length=MAX_FILENAME_LENGTH):
    """Convert a filename to ASCII characters if it contains non-ASCII characters."""
    if any(ord(char) > 127 for char in filename):
        ascii_filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')
        ascii_filename = re.sub(r'\s+', '_', ascii_filename)
        ascii_filename = re.sub(r'[^a-zA-Z0-9_\-]', '', ascii_filename)
        ascii_filename = ascii_filename[:max_length]
        logger.info(f"Converted to ASCII: {ascii_filename}")
        return ascii_filename
    return filename

def get_video_hash(video_path, chunk_size=8192, sample_size=10*1024*1024):
    """
    Calcule un hash partiel du fichier vidéo pour identifier les doublons.
    Échantillonne seulement le début, le milieu et la fin du fichier pour des performances.
    """
    if not os.path.exists(video_path):
        return None
    
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        return None
    
    hasher = hashlib.md5()
    
    # Échantillonnage stratégique: début, milieu, fin
    positions = [0]  # Début
    
    # Ajouter le milieu si le fichier est assez grand
    if file_size > sample_size:
        positions.append(file_size // 2)
    
    # Ajouter la fin si le fichier est assez grand    
    if file_size > chunk_size:
        positions.append(max(0, file_size - chunk_size))
    
    with open(video_path, 'rb') as f:
        for pos in positions:
            f.seek(pos)
            chunk = f.read(min(chunk_size, sample_size // 3))
            if not chunk:
                break
            hasher.update(chunk)
    
    return hasher.hexdigest()

def find_duplicate_by_hash(directory, video_hash, extensions=['.mp4', '.mkv', '.webm']):
    """
    Recherche des fichiers existants avec le même hash de contenu.
    """
    if not video_hash:
        return None
        
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                existing_hash = get_video_hash(file_path)
                if existing_hash == video_hash:
                    logger.info(f"Doublon trouvé par hash: {file_path}")
                    return file_path
    return None

def find_duplicate_by_size(directory, file_size, extensions=['.mp4', '.mkv', '.webm']):
    """
    Recherche des fichiers existants avec la même taille.
    """
    if file_size <= 0:
        return None
        
    candidates = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                if os.path.getsize(file_path) == file_size:
                    candidates.append(file_path)
    
    if candidates:
        logger.info(f"Candidats potentiels de même taille: {candidates}")
    
    return candidates[0] if candidates else None

def download_video(url, output_folder):
    """
    Télécharge une vidéo et gère la structure des dossiers et fichiers.
    Évite les duplications en vérifiant si la vidéo existe déjà.
    """
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Téléchargement de vidéo depuis URL: {url}")
    logger.info(f"Dossier de sortie: {output_folder}")
    
    try:
        # 1. Extraction des informations de la vidéo
        ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'logger': YTDLPLogger(),
            'nocheckcertificate': True,
            'ignoreerrors': False  # Ne pas ignorer les erreurs
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            video_id = info_dict.get('id', '')
            original_title = info_dict.get('title', 'unknown_video')
            
            logger.info(f"ID Vidéo: {video_id}")
            logger.info(f"Titre original: {original_title}")
            
            # On utilise l'ID vidéo en premier lieu pour le nommage si disponible
            if video_id:
                base_filename = f"{sanitize_filename(original_title)}_{video_id}"
            else:
                base_filename = sanitize_filename(original_title)
        
        # 2. Téléchargement dans un dossier temporaire
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Dossier temporaire: {temp_dir}")
            
            temp_output = os.path.join(temp_dir, "video.%(ext)s")
            
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'outtmpl': temp_output,
                'restrictfilenames': True,
                'nocheckcertificate': True,
                'retries': 5,
                'quiet': False,  # Afficher la progression
                'noprogress': False,  # Afficher la barre de progression
                'logger': YTDLPLogger(),  # Utiliser notre logger personnalisé
                'no_warnings': False  # Afficher les avertissements
            }
            
            logger.info("Démarrage du téléchargement...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # 3. Trouver le fichier téléchargé
            downloaded_files = list(Path(temp_dir).glob("video.*"))
            if not downloaded_files:
                raise FileNotFoundError("Aucun fichier téléchargé trouvé")
                
            temp_video_path = str(downloaded_files[0])
            video_extension = os.path.splitext(temp_video_path)[1]
            video_size = os.path.getsize(temp_video_path)
            
            logger.info(f"Fichier téléchargé: {temp_video_path}")
            logger.info(f"Taille: {video_size} octets")
            
            # 4. Vérifier si un doublon existe déjà
            # 4.1 Par taille de fichier d'abord (rapide)
            duplicate_by_size = find_duplicate_by_size(output_folder, video_size)
            
            if duplicate_by_size:
                logger.info(f"Fichier de même taille trouvé: {duplicate_by_size}")
                
                # 4.2 Vérification par hash pour confirmer (plus précis)
                video_hash = get_video_hash(temp_video_path)
                hash_of_duplicate = get_video_hash(duplicate_by_size)
                
                if video_hash == hash_of_duplicate:
                    logger.info(f"Doublons confirmés par hash. Réutilisation du fichier existant.")
                    return duplicate_by_size, original_title
            
            # 5. Si aucun doublon, créer la structure finale
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            final_filename = f"{base_filename}_{timestamp}{video_extension}"
            
            # Créer un dossier pour la vidéo si ce n'est pas déjà fait
            video_folder_name = base_filename[:40]  # Limiter la longueur du nom du dossier
            video_folder = output_path / video_folder_name
            video_folder.mkdir(exist_ok=True)
            
            # 6. Copier la vidéo dans le dossier final
            final_video_path = video_folder / final_filename
            shutil.copy2(temp_video_path, final_video_path)
            
            logger.info(f"Vidéo enregistrée avec succès: {final_video_path}")
            return str(final_video_path), original_title
        
    except Exception as e:
        logger.error(f"Erreur lors du téléchargement: {str(e)}", exc_info=True)
        raise

# Fonction pour le test local
if __name__ == "__main__":
    # Configuration du logging pour les tests
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Remplacez par une URL valide
    result = download_video(test_url, "output")
    print(f"Résultat: {result}") 
