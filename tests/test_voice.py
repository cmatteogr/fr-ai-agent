import os

from dotenv import load_dotenv
from groq import Groq


cliente = Groq(api_key=os.environ["FR_AGENT_GROQ"])


def audio_transcription(file_route: str) -> str:
    """convert voice message to text using whisper"""
    with open(file_route, "rb") as audio:
        transcription = cliente.audio.transcriptions.create(
            model="whisper-large-v3", file=audio, language="es"
        )
    return transcription.text


result = audio_transcription("audio.ogg")
print(f"transcripcion: {result}")
