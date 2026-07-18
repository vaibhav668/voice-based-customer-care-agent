import os
import sys
from unittest.mock import patch, PropertyMock

# Add backend directory to sys.path so that 'app' module can be resolved
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Apply mocks at the module level so they are active before any test files or application modules are imported
patcher_hf = patch("app.ai.rag.embeddings.MemoryEfficientEmbeddings.hf_embeddings", new_callable=PropertyMock, return_value=None)
patcher_hf.start()

class MockCommunicate:
    def __init__(self, *args, **kwargs):
        pass
    async def save(self, *args, **kwargs):
        pass

import edge_tts
edge_tts.Communicate = MockCommunicate

async def mock_generate(self, text, language="en"):
    return "generated_audio/dummy.mp3"

from app.voice.tts import TextToSpeech
TextToSpeech.generate = mock_generate

class MockFFmpegProcess:
    """Mock asyncio subprocess that returns 1 second of silence at 8kHz mono PCM16."""
    async def communicate(self):
        # 8000 samples/sec * 2 bytes/sample = 16000 bytes of silence
        return (b'\x00' * 16000, b'')

async def mock_create_subprocess_exec(*args, **kwargs):
    return MockFFmpegProcess()

import asyncio
asyncio.create_subprocess_exec = mock_create_subprocess_exec
