import asyncio
import aiohttp

from config.llm import *


class LLMManager:
    def __init__(self):
        self._stream: bool = False
        self._keep_alive: str = OLLAMA_KEEP_ALIVE
        self._timeout: int = QA_TIMEOUT
        self._host: str = OLLAMA_HOST
        self._model: str = SQL_MODEL
        self._port: int = OLLAMA_PORT

    async def call(
            self,
            url:str = None,
            model: str = None,
            prompt: str = None,
            stream: bool = False,
            keep_alive: str = None,
            temperature: float = 0.0,
            timeout: int = 0,
            warmup: bool = False,
    ):
        log_model = model if model else self._model
        self._port: int = LLM_PORT_CONFIG.get(log_model, OLLAMA_PORT)
        req_url = url if url else f"http://{self._host}:{self._port}/api/generate"

        req_timeout = timeout if timeout else self._timeout
        action_type = "warmup" if warmup else "request"

        req_json = {}
        req_json["model"] = log_model
        req_json["prompt"] = prompt if prompt else "ok"
        req_json["stream"] = stream if stream else self._stream
        req_json["keep_alive"] = keep_alive if keep_alive else self._keep_alive
        if temperature:
            req_json["temperature"] = temperature

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=req_url, 
                    json=req_json,
                    timeout=req_timeout) as response:
                    if warmup:
                        print(f"Model {log_model} warmed up")
                        return await response.text()
                    else:
                        # TODO Parse response for JSON response
                        # return resp.json()["response"]
                        response.raise_for_status()
                        llm_resp = await response.json()
                        return llm_resp["response"]
                    
        except aiohttp.ClientConnectorError as e:
            print(f"Connection error during {action_type}: {e}")
        except asyncio.TimeoutError:
            print(f"Request timed out during {action_type}")
        except aiohttp.ClientResponseError as e:
            print(f"HTTP error {e.status} during {action_type}: {e.message}")
        except Exception as e:
            print(f"Unexpected error during {action_type}: {e}")
