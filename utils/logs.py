import os
import orjson
import aiofiles
from typing import Union
from functools import partial
from fastlogging import LogInit

from config.log import FEEDBACK_LOG_FILE, LOG_FILE, LOG_LOCATION


class FileLogger:
    def __init__(self):
        self.log_file = LOG_FILE
        self.feedback_log_file = FEEDBACK_LOG_FILE
        self.log_path = self._get_log_folder()

    def get_logger(self, feedback: bool = False):
        # Fastlogging specifics
        _f = partial(LogInit, domain="Vegayan", maxSize=81920, console=False,
                    backupCnt=5, indent=(0,2,8), encoding='utf-8')
        _file = self.feedback_log_file if feedback else self.log_file
        _path = os.path.join(self.log_path, _file)
        self.logger = _f(pathName=_path)
        return self.logger

    @staticmethod
    def _get_log_folder() -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(current_dir, '..', LOG_LOCATION)
        os.makedirs(log_path, exist_ok=True)
        return log_path
        
    async def write(self, content: Union[str, dict], feedback: bool = False):
        '''Writes to log file based on input params'''
        _file = self.feedback_log_file if feedback else self.log_file
        write_to_file = os.path.join(self.log_path, _file)
        try:
            async with aiofiles.open(write_to_file, mode='a', encoding='utf-8') as f:
                await f.write(orjson.dumps(content).decode('utf-8') + "\n")
        except FileNotFoundError:
            print(f"Error: The directory for '{write_to_file}' does not exist.")
        except PermissionError:
            print(f"Error: Permission denied for '{write_to_file}'.")
        except Exception as e:
            print(f"An unexpected error occurred while writing to '{write_to_file}': {e}")