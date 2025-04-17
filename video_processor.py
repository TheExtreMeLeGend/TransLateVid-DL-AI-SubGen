#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, threading, concurrent.futures, logging
from openai import OpenAI
from utils import (
    progress_queue, command_queue,
    restore_std_redirects, enable_std_redirects,
    format_whisper_model_name
)
from video_downloader import download_video, sanitize_filename, ensure_unique_path
from audio_extractor import extract_audio, separate_audio
from transcriber import transcribe_audio
from translate import translate_srt_file, set_api_keys

class _VideoProcessorCore:
    """Noyau de traitement vidéo (séquentiel ou multi-thread)."""
    def __init__(self, config, threaded=False):
        self.config = config
        self.threaded = threaded
        self.max_workers = min(os.cpu_count() or 4, 8)
        self.update_api_client()

    def update_api_client(self):
        OpenAI(api_key=self.config.openai_key)
        set_api_keys(self.config.deepl_key, self.config.openai_key)

    def process_video(self, url=None, video_path=None,
                      target_language=None, translation_service=None, use_gpu=None):
        if not (url or video_path):
            logging.error("Aucune URL ni fichier vidéo spécifié")
            command_queue.put({"command":"error","message":"URL ou fichier requis."})
            return False
        tl = target_language or self.config.default_language.split(' - ')[0]
        svc = translation_service or self.config.default_service
        gpu = use_gpu if use_gpu is not None else self.config.use_gpu
        threading.Thread(target=self._run, args=(url, video_path, tl, svc, gpu), daemon=True).start()
        return True

    def cancel_processing(self):
        command_queue.put({"command":"cancel"})

    def _run(self, url, video_path, tl, svc, gpu):
        try:
            restore_std_redirects()
            self.update_api_client()
            ctx = self._prepare_env(url, video_path)
            enable_std_redirects()

            # Étapes 1 & 2 : Extraction + séparation en parallèle si threaded
            if self.threaded:
                with concurrent.futures.ThreadPoolExecutor(self.max_workers) as ex:
                    f1 = ex.submit(self._extract_audio, ctx, gpu, tl, svc)
                    f2 = ex.submit(self._separate_audio, ctx, gpu, tl, svc)
                    concurrent.futures.wait([f1, f2])
            else:
                self._extract_audio(ctx, gpu, tl, svc)
                self._separate_audio(ctx, gpu, tl, svc)

            # Étape 3 : Transcription
            self._transcribe_audio(ctx, gpu, tl, svc)

            # Étape 4 : Traduction
            self._translate_srt(ctx, gpu, tl, svc)

            progress_queue.put({"value":100,"status_text":"Traitement terminé !"})
            command_queue.put({"command":"processing_done","video_folder":ctx['folder']})
        except Exception as e:
            logging.error(f"Erreur : {e}", exc_info=True)
            command_queue.put({"command":"error","message":str(e)})
        finally:
            enable_std_redirects()

    def _prepare_env(self, url, video_path):
        out = self.config.output_folder
        os.makedirs(out, exist_ok=True)
        if video_path:
            title = sanitize_filename(os.path.splitext(os.path.basename(video_path))[0])
            src = video_path
        else:
            tmp, title = download_video(url, out)
            title = sanitize_filename(title)
            folder = os.path.join(out, title)
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, f"{title}.mp4")
            if os.path.exists(dest): dest = ensure_unique_path(dest)
            os.rename(tmp, dest)
            src = dest
        folder = os.path.join(out, title)
        os.makedirs(folder, exist_ok=True)
        return {"video":src, "folder":folder,
                "audio":os.path.join(folder,f"{title}.mp3"),
                "trans":os.path.join(folder,title),
                "vtrans":os.path.join(folder,f"{title}_vocal")}  

    def _extract_audio(self, ctx, gpu, tl, svc):
        progress_queue.put({"value":30,"status_text":"Extraction audio..."})
        extract_audio(ctx['video'], ctx['audio'])

    def _separate_audio(self, ctx, gpu, tl, svc):
        sep = os.path.join(ctx['folder'],'separated')
        os.makedirs(sep, exist_ok=True)
        progress_queue.put({"value":40,"status_text":"Séparation pistes..."})
        separate_audio(ctx['audio'], sep, use_gpu=gpu)
        ctx['vocal'] = os.path.join(sep,'vocals.wav')

    def _transcribe_audio(self, ctx, gpu, tl, svc):
        model = format_whisper_model_name(self.config.whisper_model)
        progress_queue.put({"value":55,"status_text":"Transcription principal..."})
        transcribe_audio(ctx['audio'], ctx['trans'], model_name=model, use_gpu=gpu)
        if ctx.get('vocal'):
            progress_queue.put({"value":70,"status_text":"Transcription vocal..."})
            transcribe_audio(ctx['vocal'], ctx['vtrans'], model_name=model, use_gpu=gpu)

    def _translate_srt(self, ctx, gpu, tl, svc):
        for base in (ctx['trans'], ctx['vtrans']):
            srt = f"{base}.srt"
            if os.path.exists(srt):
                progress_queue.put({"value":80,"status_text":f"Traduction en {tl}..."})
                out, content = translate_srt_file(srt, tl, svc)
                with open(os.path.join(ctx['folder'], os.path.basename(out)), 'w', encoding='utf-8') as f:
                    f.write(content)

class VideoProcessor:
    def __init__(self, config): self._c=_VideoProcessorCore(config,threaded=False)
    def update_api_client(self): self._c.update_api_client()
    def process_video(self,*a,**k): return self._c.process_video(*a,**k)
    def cancel_processing(self): return self._c.cancel_processing()

class ThreadedVideoProcessor:
    def __init__(self, config): self._c=_VideoProcessorCore(config,threaded=True)
    def update_api_client(self): self._c.update_api_client()
    def process_video(self,*a,**k): return self._c.process_video(*a,**k)
    def cancel_processing(self): return self._c.cancel_processing()
