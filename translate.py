import requests
import json
import os
import logging
import concurrent.futures
from openai import OpenAI
from utils import config  # ✅ Ajout

# Configuration du logger
logger = logging.getLogger(__name__)
for lib in ["httpx", "httpcore", "openai", "urllib3", "requests"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

# Clés API initialisées à des valeurs par défaut
deepl_key = ""
openai_key = ""
client = None

def set_api_keys(deepl, openai_api_key):
    global deepl_key, openai_key, client
    deepl_key = deepl
    openai_key = openai_api_key
    client = OpenAI(api_key=openai_key)

def translate_text_deepl(text, target_language):
    logger.info(f"\n📤 [DeepL] Envoi de la phrase à traduire ({target_language}) :\n{text}")
    url = "https://api-free.deepl.com/v2/translate"
    headers = {
        "Authorization": f"DeepL-Auth-Key {deepl_key}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "text": text,
        "target_lang": target_language.upper()
    }
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        result = response.json()
        translation = result['translations'][0]['text']
        logger.info(f"\n📥 [DeepL] Traduction reçue :\n + {translation}")
        return translation
    else:
        raise Exception(f"DeepL API error: {response.status_code} {response.text}")

def translate_text_openai(text, target_language):
    logger.info(f"\n📤 [OpenAI] Envoi de la phrase à traduire ({target_language}) :\n{text}")
    prompt = (
        "Attention : la transcription automatique peut contenir des erreurs. "
        "Veillez à ce que la phrase traduite soit cohérente dans son contexte, "
        "en corrigeant les éventuelles coquilles si nécessaire. "
        "Assurez-vous que la traduction est précise et préserve le sens original. "
        "Ne fournissez aucun commentaire, explication ou formatage supplémentaire. "
        f"La traduction doit être en {target_language} :\n\n{text}"
    )

    messages = [
        {"role": "assistant", "content": "Vous êtes un traducteur très compétent."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="o3-mini",
        messages=messages,
        reasoning_effort="low"
    )
    translation = response.choices[0].message.content
    logger.info(f"\n📥 [OpenAI] Traduction reçue :\n{translation}")
    return translation

def translate_text_o3(text, target_language):
    logger.info(f"\n📤 [O3] Envoi de la phrase à traduire ({target_language}) :\n{text}")
    prompt = (
        "Attention : la transcription automatique peut contenir des erreurs. "
        "Veillez à ce que la phrase traduite soit cohérente dans son contexte, "
        "en corrigeant les éventuelles coquilles si nécessaire. "
        "Assurez-vous que la traduction est précise et préserve le sens original. "
        "Ne fournissez aucun commentaire, explication ou formatage supplémentaire. "
        f"La traduction doit être en {target_language} :\n\n{text}"
    )

    messages = [
        {"role": "assistant", "content": "Vous êtes un traducteur très compétent."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="o3-mini",
        messages=messages,
        reasoning_effort="low"
    )
    translation = response.choices[0].message.content
    logger.info(f"\n📥 [O3] Traduction reçue :\n{translation}")
    return translation

def verify_translation(segment, target_language):
    prompt = (
        f"Verify if the following translation is completely in {target_language} "
        f"and has no words from the original language. "
        f"Return 'yes' if it is accurate and 'no' otherwise:\n\n{segment}"
    )

    messages = [
        {"role": "assistant", "content": "You are a translation quality checker."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="o3-mini",
        messages=messages,
        reasoning_effort="low"
    )
    result = response.choices[0].message.content
    return 'yes' in result.lower()

def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def write_file(file_path, content):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)

def translate_srt_file(srt_path, target_language, service='openai', mode='batched', use_threading=None):
    """
    Translate an SRT file using the specified translation service and mode.

    :param srt_path: Path to the input SRT file
    :param target_language: Target language code (e.g., 'FR' for French)
    :param service: Translation service to use ('deepl', 'openai', 'o3')
    :param mode: Translation mode ('batched' or 'threaded')
    :param use_threading: Bool to override config.use_threading if specified
    :return: Tuple containing translated file path and translated content
    """
    if use_threading is None:
        use_threading = config.use_threading  # ✅ lire depuis la config si non spécifié

    if use_threading and mode == 'threaded':
        return translate_srt_file_threaded(srt_path, target_language, service)
    else:
        return translate_srt_file_batched(srt_path, target_language, service)

def translate_srt_file_threaded(srt_path, target_language, service, max_workers=4):
    content = read_file(srt_path)
    segments = content.split('\n\n')

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        segment_data = []

        for segment in segments:
            lines = segment.split('\n')
            if len(lines) >= 2:
                segment_number = lines[0]
                timecodes = lines[1]
                text_to_translate = '\n'.join(lines[2:]) if len(lines) > 2 else ""

                if text_to_translate.strip():
                    if service.lower() == "deepl":
                        future = executor.submit(translate_text_deepl, text_to_translate, target_language)
                    elif service.lower() in ("o3", "o3-mini"):
                        future = executor.submit(translate_text_o3, text_to_translate, target_language)
                    else:
                        future = executor.submit(translate_text_openai, text_to_translate, target_language)

                    futures.append(future)
                    segment_data.append((segment_number, timecodes, text_to_translate, True))
                else:
                    segment_data.append((segment_number, timecodes, "", False))

        future_index = 0
        translated_segments = []

        for segment_info in segment_data:
            segment_number, timecodes, text, needs_translation = segment_info
            if needs_translation:
                translated_text = futures[future_index].result()
                future_index += 1
                translated_segment = f"{segment_number}\n{timecodes}\n{translated_text}"
            else:
                if text:
                    translated_segment = f"{segment_number}\n{timecodes}\n{text}"
                else:
                    translated_segment = f"{segment_number}\n{timecodes}"
            translated_segments.append(translated_segment)

    translated_content = '\n\n'.join(translated_segments)
    translated_path = srt_path.replace('.srt', f'_translated_{target_language}.srt')
    write_file(translated_path, translated_content)
    return translated_path, translated_content

def translate_srt_file_batched(srt_path, target_language, service, batch_size=10):
    content = read_file(srt_path)
    segments = content.split('\n\n')
    translated_content = ""

    for i in range(0, len(segments), batch_size):
        batch_segments = segments[i:i + batch_size]
        batch_text = "\n\n".join(batch_segments)

        if service.lower() in ("o3", "o3-mini"):
            translated_batch = translate_text_o3(batch_text, target_language)
            retries = 3
            while not verify_translation(translated_batch, target_language) and retries > 0:
                translated_batch = translate_text_o3(batch_text, target_language)
                retries -= 1
        elif service.lower() == "deepl":
            batch_translated_segments = []
            for segment in batch_segments:
                translated_segment = translate_text_deepl(segment, target_language)
                batch_translated_segments.append(translated_segment)
            translated_batch = "\n\n".join(batch_translated_segments)
        else:
            translated_batch = translate_text_openai(batch_text, target_language)

        if i > 0:
            translated_content += "\n\n"
        translated_content += translated_batch

    translated_path = srt_path.replace('.srt', f'_translated_{target_language}.srt')
    write_file(translated_path, translated_content)
    return translated_path, translated_content
