import requests
import json
import os
import logging
import concurrent.futures
from openai import OpenAI
from utils import config  # ✅ Added

# Logger configuration
logger = logging.getLogger(__name__)
for lib in ["httpx", "httpcore", "openai", "urllib3", "requests"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

# Default API keys
deepl_key = ""
openai_key = ""
client = None

def set_api_keys(deepl, openai_api_key):
    global deepl_key, openai_key, client
    deepl_key = deepl
    openai_key = openai_api_key
    client = OpenAI(api_key=openai_key)

def translate_text_deepl(text, target_language):
    logger.info(f"\n📤 [DeepL] Sending text to translate ({target_language}):\n{text}")
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
        logger.info(f"\n📥 [DeepL] Translation received:\n{translation}")
        return translation
    else:
        raise Exception(f"DeepL API error: {response.status_code} {response.text}")

def translate_text_openai(text, target_language):
    logger.info(f"\n📤 [OpenAI] Sending text to translate ({target_language}):\n{text}")
    prompt = (
        "Note: The automatic transcription may contain errors. "
        "Please ensure the translated sentence makes sense in context, "
        "correcting any mistakes as needed. "
        "Provide an accurate translation that preserves the original meaning, "
        "without any additional comments or formatting. "
        f"The translation should be in {target_language}:\n\n{text}"
    )

    messages = [
        {"role": "assistant", "content": "You are a highly skilled translator."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="o3-mini",
        messages=messages,
        reasoning_effort="low"
    )
    translation = response.choices[0].message.content
    logger.info(f"\n📥 [OpenAI] Translation received:\n{translation}")
    return translation

def translate_text_o3(text, target_language):
    logger.info(f"\n📤 [O3] Sending text to translate ({target_language}):\n{text}")
    prompt = (
        "Note: The automatic transcription may contain errors. "
        "Please ensure the translated sentence makes sense in context, "
        "correcting any mistakes as needed. "
        "Provide an accurate translation that preserves the original meaning, "
        "without any additional comments or formatting. "
        f"The translation should be in {target_language}:\n\n{text}"
    )

    messages = [
        {"role": "assistant", "content": "You are a highly skilled translator."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="o3-mini",
        messages=messages,
        reasoning_effort="low"
    )
    translation = response.choices[0].message.content
    logger.info(f"\n📥 [O3] Translation received:\n{translation}")
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
        use_threading = config.use_threading

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

        translated_segments = []
        for idx, (segment_number, timecodes, text, needs) in enumerate(segment_data):
            if needs:
                translation = futures[idx].result()
                translated_segments.append(f"{segment_number}\n{timecodes}\n{translation}")
            else:
                translated_segments.append(f"{segment_number}\n{timecodes}\n{text}")

    translated_content = '\n\n'.join(translated_segments)
    translated_path = srt_path.replace('.srt', f'_translated_{target_language}.srt')
    write_file(translated_path, translated_content)
    return translated_path, translated_content

def translate_srt_file_batched(srt_path, target_language, service, batch_size=10):
    content = read_file(srt_path)
    segments = content.split('\n\n')
    translated_content = ""

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        batch_text = "\n\n".join(batch)

        if service.lower() in ("o3", "o3-mini"):
            translated_batch = translate_text_o3(batch_text, target_language)
            retries = 3
            while not verify_translation(translated_batch, target_language) and retries > 0:
                translated_batch = translate_text_o3(batch_text, target_language)
                retries -= 1
        elif service.lower() == "deepl":
            translated_batch = "\n\n".join(translate_text_deepl(seg, target_language) for seg in batch)
        else:
            translated_batch = translate_text_openai(batch_text, target_language)

        if i > 0:
            translated_content += "\n\n"
        translated_content += translated_batch

    translated_path = srt_path.replace('.srt', f'_translated_{target_language}.srt')
    write_file(translated_path, translated_content)
    return translated_path, translated_content
