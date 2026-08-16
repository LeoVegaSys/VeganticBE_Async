import json
from aiohttp import web
import aiohttp_cors

from config.server import SERVER_HOST
from src.startpoint.graph import WorkflowManager
from utils.context import QueryRequest



async def handle_query(request):
    try:
        data = await request.json()
        obj = QueryRequest(body=data)
        if not obj:
            return web.json_response(
                {"error": "Invalid request structure"},
                status=400  # Bad Request
            )
        res = await WorkflowManager().answer_query(req=obj)
        payload = json.dumps(res, default=str)
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON"},
            status=400  # Bad Request
        )
    except Exception as e:
        return web.json_response(
            {"error": str(e)},
            status=500
            )


async def handle_feedback(request):
    data = await request.json()
    return web.json_response({"received": data})


# 3. Setup the Application and Routes
async def init_app():
    app = web.Application()
    app.add_routes([
        web.post('/ask', handle_query),
        web.post('/feedback', handle_feedback)
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