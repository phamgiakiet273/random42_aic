"""Vietnamese speech-to-text: VAD segmentation + Wav2Vec2 CTC + n-gram beam search decoding."""

import math
import os
import subprocess
from collections import OrderedDict

import numpy as np
import pydub
import torch
from pyannote.audio import Model
from pyannote.audio.pipelines import VoiceActivityDetection
from pyctcdecode import Alphabet, BeamSearchDecoderCTC, LanguageModel
from pydub import AudioSegment
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

import kenlm

from src.utils.settings import get_settings


class SpeechToText:
    def __init__(self, ngram_lm_path: str, hf_token: str | None = None):
        """
        Args:
            ngram_lm_path (str): Path to the KenLM n-gram .bin file used for beam search decoding.
            hf_token (str | None): HuggingFace hub token. Defaults to settings.huggingface_hub_token.
        """
        self.device = "cuda"
        hf_token = hf_token or get_settings().huggingface_hub_token

        # load processor and model for speech to text
        self.processor = Wav2Vec2Processor.from_pretrained(
            "phamgiakiet273/wav2vec2-base-vi-vlsp530h",
            use_auth_token=hf_token,
        )
        self.model = Wav2Vec2ForCTC.from_pretrained(
            "phamgiakiet273/wav2vec2-base-vi-vlsp530h",
            use_auth_token=hf_token,
        ).to(self.device)

        # init language model decoder
        self.lm_file = ngram_lm_path
        self.ngram_lm_model = self.get_decoder_ngram_model(
            self.processor.tokenizer, self.lm_file
        )

        # init audio model and pipeline for voice activity detection
        self.audio_model = Model.from_pretrained(
            "pyannote/segmentation",
            use_auth_token=hf_token,
        ).to(self.device)
        self.audio_pipeline = VoiceActivityDetection(
            segmentation=self.audio_model, device=torch.device(self.device)
        )
        hyper_parameters = {
            # onset/offset activation thresholds
            "onset": 0.5,
            "offset": 0.5,
            # remove speech regions shorter than that many seconds.
            "min_duration_on": 0.5,
            # fill non-speech regions shorter than that many seconds.
            "min_duration_off": 0.0,
        }
        self.audio_pipeline.instantiate(hyper_parameters)

    def get_decoder_ngram_model(self, tokenizer, ngram_lm_path: str):
        """Load a beam-search CTC decoder backed by the KenLM n-gram model."""
        vocab_dict = tokenizer.get_vocab()
        sort_vocab = sorted((value, key) for (key, value) in vocab_dict.items())
        vocab_list = [x[1] for x in sort_vocab][:-2]
        vocab_list[tokenizer.pad_token_id] = ""
        vocab_list[tokenizer.unk_token_id] = ""
        vocab_list[tokenizer.word_delimiter_token_id] = " "
        alphabet = Alphabet.build_alphabet(
            vocab_list, ctc_token_idx=tokenizer.pad_token_id
        )
        lm_model = kenlm.Model(ngram_lm_path)
        decoder = BeamSearchDecoderCTC(alphabet, language_model=LanguageModel(lm_model))
        return decoder

    def read(self, f: str, normalized: bool = True):
        """Read a wav/mp3 file and return (frame_rate, samples)."""
        a = pydub.AudioSegment.from_mp3(f)
        y = np.array(a.get_array_of_samples())
        if a.channels == 2:
            y = y.reshape((-1, 2))
        if normalized:
            return a.frame_rate, np.float32(y) / 2**15
        else:
            return a.frame_rate, y

    def audio_to_vector(self, audio_path: str) -> np.ndarray:
        """Convert an audio file to a normalized sample vector."""
        sr, x = self.read(audio_path)
        return x

    def speech_to_text(self, audio_path: str) -> str:
        """Return the transcript for a 16kHz mono .wav file via beam search decoding."""
        audio_vector = self.audio_to_vector(audio_path)
        inputs = self.processor(
            audio_vector, sampling_rate=16_000, return_tensors="pt"
        ).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs).logits
        transcription = self.ngram_lm_model.decode(
            outputs.cpu().detach().numpy()[0], beam_width=500
        )
        return transcription

    def video_to_text(self, video_path: str, wav_path: str) -> OrderedDict:
        """Return {(start,end) str : transcript} for a video, splitting speech-active .wav segments into wav_path."""
        video_name = os.path.basename(video_path)
        total_wav_path = wav_path + str(video_name).replace(".mp4", "") + ".wav"
        if not os.path.exists(total_wav_path):
            command = (
                "ffmpeg -y -i " + video_path + " -ac 1 -ar 16000 " + total_wav_path
            )
            subprocess.call(command, shell=True)
        video_speech_region = self.audio_pipeline(total_wav_path)
        video_audio = AudioSegment.from_wav(total_wav_path)
        video_transcript = {}
        for speech in video_speech_region.get_timeline().support():
            # active speech between speech.start and speech.end
            start = math.floor(speech.start)
            end = math.ceil(speech.end)
            cur_audio = video_audio[start * 1000 : end * 1000 + 1]
            cur_audio_path = wav_path + "speech" + str(start) + "-" + str(end) + ".wav"
            cur_audio.export(cur_audio_path, format="wav")
            transcription = self.speech_to_text(cur_audio_path)
            video_transcript[str(str(start) + "_" + str(end))] = transcription
        return OrderedDict(video_transcript)
