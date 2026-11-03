import aiohttp

from config.graph_rag import GRF_RAG_HOST, GRF_RAG_PORT, GRF_RAG_ENDPT
from config.doc_rag import DOC_RAG_HOST, DOC_RAG_PORT, DOC_RAG_ENDPT


async def query_rag(question: str):
    """Pass user query to RAG and process response"""
    # url = f"http://{GRF_RAG_HOST}:{GRF_RAG_PORT}/{GRF_RAG_ENDPT}"
    url = f"http://{DOC_RAG_HOST}:{DOC_RAG_PORT}/{DOC_RAG_ENDPT}"
    json_data = {"question": question}
    headers = {
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=json_data, headers=headers) as response:
            response.raise_for_status()  # Raise exception for 4xx/5xx status codes
            result = await response.json()
            print(f"Status: {response.status}")
            print(f"Response: {result}")
    return result
