import json
import orjson
from aiohttp import web
import aiohttp_cors

from config.server import SERVER_HOST
from src.start_with_rag.graph import RAGWorkflowManager
from src.startpoint.graph import WorkflowManager
from utils.context import (QueryRequest, SummarizeRequest)
from utils.summarization import perform

from server.user_session_mgmt_apis import (
    log_in_user, user_details, user_sessions, add_new_session,
    session_details, delete_session, update_session, clear_session
)



async def process_query(request):
    try:
        data = await request.json()
        # call langgraph workflow start func here
        result = RAGWorkflowManager().answer_query(data=data)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_query(request):
    try:
        data = await request.json()
        obj = QueryRequest(body=data)
        if not obj:
            return web.json_response(
                {"error": "Invalid request structure"}, status=400)
        res = await WorkflowManager().answer_query(obj)
        payload = orjson.dumps(res).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except orjson.JSONEncodeError:
        return web.json_response(
            {"error": "Unable to load into JSON"}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_feedback(request):
    data = await request.json()
    return web.json_response({"feedback received": data})


async def summarize_chat(request):
    try:
        data = await request.json()
        obj = SummarizeRequest(body=data)
        if not obj:
            return web.json_response(
                {"error": "Invalid request structure"}, status=400)
        res = await perform(obj)
        payload = orjson.dumps(res).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except orjson.JSONEncodeError:
        return web.json_response(
            {"error": "Unable to load into JSON"}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)




# 3. Setup the Application and Routes
async def init_app():
    app = web.Application()
    app.add_routes([
        web.post('/query', process_query),
        web.post('/ask', handle_query),
        web.post('/summarize', summarize_chat),
        web.post('/feedback', handle_feedback),
        web.get('/auth/login', log_in_user),
        web.get('/auth/me', user_details),
        web.get('/sessions', user_sessions),
        web.get('/sessions/{sessionId}/messages', session_details),
        web.post('/sessions', add_new_session),
        web.delete('/sessions/{sessionId}', delete_session),
        web.patch('/sessions/clear/{sessionId}', clear_session),
        web.patch('/sessions/update/{sessionId}', update_session),
    ])

    # Configure CORS
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    # Attach CORS to specific routes
    for route in list(app.router.routes()):
        cors.add(route)

    return app


# 4. Run the server on a specific port
def serve(port):
# if __name__ == '__main__':
    # web.run_app manages the asyncio event loop automatically
    # Set host='127.0.0.1' and port=8080 as requested
    web.run_app(init_app(), host=SERVER_HOST, port=port)