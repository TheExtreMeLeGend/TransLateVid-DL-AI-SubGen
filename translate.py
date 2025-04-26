import re
import requests
import json
import os
import logging
import concurrent.futures
from openai import OpenAI
from utils import config

# Logger configuration
logger = logging.getLogger(__name__)
for lib in ["httpx", "httpcore", "openai", "urllib3", "requests"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

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


def parse_srt_segments(srt_content):
    # regex segments {num}\n{time}\n{text (peut être multi lignes)}
    pattern = re.compile(
        r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3})\n(.*?)(?=\n\d+\n|\Z)', 
        re.DOTALL)
    segments = []
    last_idx = 0
    for m in pattern.finditer(srt_content):
        if m.start() > last_idx:
            bloc = srt_content[last_idx:m.start()].strip()
            if bloc:
                segments.append({"number": None, "timecode": None, "text": bloc})
        segments.append({
            "number": m.group(1),
            "timecode": m.group(2),
            "text": m.group(3).strip()
        })
        last_idx = m.end()
    if last_idx < len(srt_content):
        bloc = srt_content[last_idx:].strip()
        if bloc:
            segments.append({"number": None, "timecode": None, "text": bloc})
    return segments

def reconstruct_srt(segments, translated_texts):
    out_lines = []
    idx_trans = 0
    for seg in segments:
        if seg["number"] is None:
            out_lines.append(translated_texts[idx_trans])
            idx_trans += 1
        else:
            out_lines.append(str(seg["number"]))
            out_lines.append(seg["timecode"])
            out_lines.append(translated_texts[idx_trans] if seg["text"] else "")
            idx_trans += 1
        out_lines.append("")
    return "\n".join(out_lines).strip()


def translate_srt_file(srt_path, target_language, service='openai', mode='batched', use_threading=None):
    if use_threading is None:
        use_threading = config.use_threading

    if use_threading and mode == 'threaded':
        return translate_srt_file_threaded(srt_path, target_language, service)
    else:
        return translate_srt_file_batched(srt_path, target_language, service)

def translate_srt_file_batched(srt_path, target_language, service, batch_size=10):
    content = read_file(srt_path)
    segments = parse_srt_segments(content)
    translated_texts = []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        # batch_texts est la liste de tous les textes de ce batch y compris les orphelins
        batch_texts = [seg["text"] for seg in batch]
        result_batch = []

        if service.lower() in ("o3", "o3-mini"):
            # Traduire batch complet groupé (si tous les batch_text sont non vides)
            for text in batch_texts:
                if text.strip():
                    translation = translate_text_o3(text, target_language)
                    retries = 3
                    while not verify_translation(translation, target_language) and retries > 0:
                        translation = translate_text_o3(text, target_language)
                        retries -= 1
                    result_batch.append(translation)
                else:
                    result_batch.append("")
        elif service.lower() == "deepl":
            for text in batch_texts:
                if text.strip():
                    result_batch.append(translate_text_deepl(text, target_language))
                else:
                    result_batch.append("")
        else:
            for text in batch_texts:
                if text.strip():
                    result_batch.append(translate_text_openai(text, target_language))
                else:
                    result_batch.append("")
        translated_texts.extend(result_batch)

    translated_content = reconstruct_srt(segments, translated_texts)
    translated_path = srt_path.replace('.srt', f'_translated_{target_language}.srt')
    write_file(translated_path, translated_content)
    return translated_path, translated_content

def translate_srt_file_threaded(srt_path, target_language, service, max_workers=4):
    content = read_file(srt_path)
    segments = parse_srt_segments(content)
    translated_texts = [None]*len(segments)

    def translate_one(idx, text):
        if not text.strip():
            return ""
        if service.lower() == "deepl":
            return translate_text_deepl(text, target_language)
        elif service.lower() in ("o3", "o3-mini"):
            translation = translate_text_o3(text, target_language)
            retries = 3
            while not verify_translation(translation, target_language) and retries > 0:
                translation = translate_text_o3(text, target_language)
                retries -= 1
            return translation
        else:
            return translate_text_openai(text, target_language)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_dict = {
            executor.submit(translate_one, idx, seg["text"]): idx
            for idx, seg in enumerate(segments)
        }
        for future in concurrent.futures.as_completed(future_dict):
            idx = future_dict[future]
            translated_texts[idx] = future.result()

    translated_content = reconstruct_srt(segments, translated_texts)
    translated_path = srt_path.replace('.srt', f'_translated_{target_language}.srt')
    write_file(translated_path, translated_content)
    return translated_path, translated_content
