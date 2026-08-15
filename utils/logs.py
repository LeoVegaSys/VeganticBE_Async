from typing import Union

import os
import json
import aiofiles

from config.log import FEEDBACK_LOG_FILE, LOG_FILE, LOG_LOCATION


class FileLogger:
    def __init__(self):
        self.log_file = LOG_FILE
        self.feedback_log_file = FEEDBACK_LOG_FILE
        self.log_path = self.get_log_folder()

    @staticmethod
    def get_log_folder() -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, '..', LOG_LOCATION)
        
    async def write_to_log(self, content: Union[str, dict], feedback: bool = False):
        '''Writes to log file based on input params'''
        _file = self.feedback_log_file if feedback else self.log_file
        write_to_file = os.path.join(self.log_path, _file)
        try:
            async with aiofiles.open(write_to_file, mode='a', encoding='utf-8') as f:
                await f.write(json.dumps(content, default=str) + "\n")
        except FileNotFoundError:
            print(f"Error: The directory for '{write_to_file}' does not exist.")
        except PermissionError:
            print(f"Error: Permission denied for '{write_to_file}'.")
        except Exception as e:
            print(f"An unexpected error occurred while writing to '{write_to_file}': {e}")