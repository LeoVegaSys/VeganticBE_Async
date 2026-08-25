from utils.context import SummarizeRequest
from utils.store import get_conversation_history
from managers.models.llm import LLMManager
from config.llm import SUMMARIZE_MODEL

async def perform(req: SummarizeRequest):
    """
    Collects request IDs, session ID and user ID.
    Parses store keys for questions (_q) and answers (_a) w.r.t. above IDs
    Creates conversation history
    Passes to SUMMARIZE MODEL
    Returns model response
    """
    conversations = []
    memories = await get_conversation_history(user_id=req.user_id,
                                              params=["question", "answer"])
    memory_map = {}
    for m in memories:
        memory_map[m.key] = m.value

    for r_id in req.request_ids:
        _key_prefix = f"{r_id.lower()}_{req.session_id.lower()}_{req.user_idlower()}"
        # Process below 2 to get values of resulting dicts
        conversations.append(('human', memory_map[f"{_key_prefix}_q"]))
        conversations.append(('ai', memory_map[f"{_key_prefix}_a"]))

    ## Get summarization prompt with conversation placeholder
    summarize_prompt = ""
    summary = await LLMManager().call(
        prompt=summarize_prompt, model=SUMMARIZE_MODEL, temperature=0.0)
    return summary
    

