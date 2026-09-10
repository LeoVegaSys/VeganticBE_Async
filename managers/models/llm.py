import asyncio
import aiohttp

from config.llm import *
from managers.models.llm_pool import get_available_port
from utils.memoization import memoize, memoization_configuration as m_cfg
from utils.logs import FileLogger


class LLMManager:
    def __init__(self):
        self._stream: bool = False
        self._keep_alive: str = OLLAMA_KEEP_ALIVE
        self._timeout: int = QA_TIMEOUT
        self._host: str = OLLAMA_HOST
        self._model: str = SQL_MODEL
        self._port: int = OLLAMA_PORT
        self.log = FileLogger().get_logger()


    @memoize(configuration=m_cfg)
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
        self._host, self._port = get_available_port(log_model)
        # self._port: int = LLM_PORT_CONFIG.get(log_model, OLLAMA_PORT)
        req_url = url if url else f"http://{self._host}:{self._port}/api/generate"

        req_timeout = timeout if timeout else self._timeout
        action_type = "warmup" if warmup else "request"

        req_json = {}
        req_json["model"] = log_model
        req_json["prompt"] = prompt if prompt else "ok"
        req_json["stream"] = stream if stream else self._stream
        req_json["keep_alive"] = keep_alive if keep_alive else self._keep_alive
        req_json["think"] = False
        req_json["options"] = {}
        if temperature:
            req_json["options"]["temperature"] = temperature
        if CONTEXT_LEN:
            req_json["options"]["num_ctx"] = CONTEXT_LEN
        if PREDICT_LEN:
            req_json["options"]["num_predict"] = PREDICT_LEN

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url=req_url, 
                    json=req_json,
                    timeout=req_timeout) as response:
                    if warmup:
                        self.log.debug(f"Model {log_model} warmed up")
                        return await response.text()
                    else:
                        # TODO Parse response for JSON response
                        # return resp.json()["response"]
                        response.raise_for_status()
                        llm_resp = await response.json()
                        self.log_llm_metrics(llm_resp)
                        self.log.debug(f"Model {log_model} returned : {llm_resp['response']}")
                        return llm_resp["response"]
                    
        except aiohttp.ClientConnectorError as e:
            self.log.error(f"Connection error during {action_type}: {e}")
        except asyncio.TimeoutError:
            self.log.error(f"Request timed out during {action_type}")
        except aiohttp.ClientResponseError as e:
            self.log.error(f"HTTP error {e.status} during {action_type}: {e.message}")
        except Exception as e:
            self.log.error(f"Unexpected error during {action_type}: {e}")

    def log_llm_metrics(self, response: dict):
        """
        Sample input:
        {'model': 'llama3.2:3b', 'created_at': '2026-09-09T06:55:42.307003949Z',
         'response': "['AP', 'MPCG', 'MUM', 'TN']", 'done': True, 'done_reason': 'stop',
         'context': [128006, 9125, 128007, 271, 38766, 1303, 33025, 2696, 25, 6790, 220, 2366, 18, 271, 128009, 128006, 882, 128007, 271, 2374, 25, 1472, 527, 264, 60505, 5782, 34, 1121, 29385, 3213, 382, 16533, 279, 14194, 91022, 1701, 27785, 279, 29636, 627, 12, 2893, 64694, 11, 5933, 11, 323, 6089, 9959, 627, 12, 86248, 3062, 15086, 11, 2819, 11, 17150, 11, 36595, 11, 477, 18845, 627, 12, 5560, 8475, 8316, 26, 5625, 735, 32280, 311, 80575, 16169, 32280, 994, 5505, 627, 12, 23497, 50549, 871, 1041, 4, 439, 264, 4461, 51451, 7826, 54, 4360, 627, 12, 3234, 539, 10552, 8029, 477, 13454, 279, 2539, 1121, 627, 12, 15037, 17459, 7554, 2038, 627, 12, 1442, 279, 1121, 4250, 4320, 279, 3488, 11, 1614, 1148, 374, 7554, 382, 6584, 91022, 25, 1160, 682, 12960, 5144, 198, 34, 49870, 25, 2570, 26264, 4532, 14430, 25, 62853, 26264, 3332, 2599, 37609, 26264, 3332, 44, 4977, 38, 37609, 26264, 3332, 44, 2864, 37609, 26264, 3332, 30271, 9388, 933, 128009, 128006, 78191, 128007, 271, 681, 2599, 518, 364, 44, 4977, 38, 518, 364, 44, 2864, 518, 364, 30271, 663], 
         'total_duration': 1956388744, 'load_duration': 1710526550, 'prompt_eval_count': 167,
         'prompt_eval_duration': 70318000, 'eval_count': 16, 'eval_duration': 173623000}
        """
        try:
            ns2s = 1e+9 # Convert nanoseconds to seconds
            total_d = round(response['total_duration']/ns2s, 3)
            load_d = round(response['load_duration']/ns2s, 3)
            prt_eval_d = round(response['prompt_eval_duration']/ns2s, 3)
            eval_d = round(response['eval_duration']/ns2s, 3)
            prt_eval_c = response['prompt_eval_count']
            eval_c = response['eval_count']
            model = response['model']
            cre_t = response['created_at']

            log_msg = f"{cre_t} : Model {model} responded with {eval_c} tokens for {prt_eval_c} prompt tokens. Completed in {total_d}s, loaded in {load_d}s, prompt evaluated in {prt_eval_d}s and result evaluated in {eval_d}s"
            self.log.debug(log_msg)

        except Exception as e:
            self.log.error(f"LLM Response metrics logging failed with error : {str(e)}")
