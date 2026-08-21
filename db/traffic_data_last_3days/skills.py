import os
import aiofiles

from utils.memoization import memoize, memoization_configuration as m_cfg


QA_BUSINESS_FACTS="business_facts.md"

FALLBACK_BUSINESS_FACTS="""
DOMAIN: (business_facts.md not found — running with no domain rules loaded.
Set appropriate QA_BUSINESS_FACTS in .env OR place business_facts.md in skills folder.)
"""

@memoize(configuration=m_cfg)
async def get_content(skills_file_name : str, skills_folder_name: str = "skills"):
    # Join path and filename
    current_dir = os.path.dirname(os.path.abspath(__file__))
    skills_dir = os.path.join(current_dir, skills_folder_name)
    skills_file = os.path.join(skills_dir, skills_file_name)
    
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