#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script pour migrer vers la nouvelle structure de projet.
"""

import os
import shutil
import sys

def create_directory_structure():
    """Crée la structure de répertoires pour le nouveau projet."""
    directories = [
        "logs",
        "output"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Répertoire créé: {directory}")

def create_gitignore():
    """Crée un fichier .gitignore pour le projet."""
    gitignore_content = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Logs
logs/
*.log

# API keys
api_keys.json
config.json

# Output files
output/

# Distribution / packaging
dist/
build/
*.egg-info/

# Virtual environments
venv/
env/
ENV/

# OS specific files
.DS_Store
Thumbs.db
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("Fichier .gitignore créé")

def check_files():
    """Vérifie si les fichiers nécessaires existent."""
    required_files = [
        "audio_extractor.py",
        "transcriber.py",
        "translate.py",
        "video_downloader.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("Les fichiers suivants sont manquants:")
        for file in missing_files:
            print(f"  - {file}")
        
        response = input("Voulez-vous continuer quand même? (o/N): ")
        if response.lower() != 'o':
            print("Migration annulée")
            sys.exit(1)

def main():
    """Fonction principale."""
    print("Migration vers la nouvelle structure de projet...")
    
    # Vérifier les fichiers requis
    check_files()
    
    # Créer la structure de répertoires
    create_directory_structure()
    
    # Créer le fichier .gitignore
    create_gitignore()
    
    print("\nMigration terminée avec succès!")
    print("\nÉtapes suivantes:")
    print("1. Créez votre dépôt GitHub:")
    print("   git init")
    print("   git add .")
    print("   git commit -m \"Initial commit\"")
    print("   git remote add origin https://github.com/votre-username/srt-translator.git")
    print("   git push -u origin main")
    print("\n2. Installez les dépendances:")
    print("   pip install -r requirements.txt")
    print("\n3. Lancez l'application:")
    print("   python app.py")

if __name__ == "__main__":
    main()
