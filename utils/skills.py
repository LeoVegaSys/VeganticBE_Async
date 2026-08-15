import os
import aiofiles

from config.skills import FALLBACK_BUSINESS_FACTS, QA_BUSINESS_FACTS


async def get_content(skills_file_name : str, skills_folder_name: str = "skills"):
    # Join path and filename
    current_dir = os.path.dirname(os.path.abspath(__file__))
    adjacent_dir = os.path.join(current_dir, '..', skills_folder_name)
    skills_file = os.path.join(adjacent_dir, skills_file_name)
    
    # Asynchronously read the file
    async with aiofiles.open(skills_file, mode='r') as f:
        content = await f.read()
        # print(f"File {skills_file} :: content :: \n {content}")
        return content


async def get_business():
    try:
        return await get_content(skills_file_name=QA_BUSINESS_FACTS)
    except FileNotFoundError:
        print(f"File {QA_BUSINESS_FACTS} not found — using fallback")
        return FALLBACK_BUSINESS_FACTS
    except Exception as e:
        print(f"Could not load business facts from {QA_BUSINESS_FACTS}: {e} — using fallback")
        return FALLBACK_BUSINESS_FACTS