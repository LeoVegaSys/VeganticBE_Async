import json
import orjson
from aiohttp import web

from utils.user_session_mgmt import (
    get_user_details, get_user_sessions, update_session_details,
    clear_conversation, delete_session_details, get_next_section_label,
    create_new_session, get_old_session, user_auth
)



async def log_in_user(request):
    try:
        data = await request.json()
        if not ('username' in data.keys() and 'password' in data.keys()):
            return web.json_response(
                {"error": "Username and password are required"}, status=400)
        result = await user_auth(data)
        if not result:
            return web.json_response(
                {"error": "Invalid username or password"}, status=401)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def user_details(request):
    try:
        data = await request.json()
        result = await get_user_details(data)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def user_sessions(request):
    try:
        data = await request.json()
        result = await get_user_sessions(data)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def add_new_session(request):
    try:
        data = await request.json()
        result = await create_new_session(data)
        # session_id = int(request.match_info['sessionId'])
        ### Call func to get session messages details here
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def session_details(request):
    try:
        # get user_id from jwt
        user_id = 0
        session_id = int(request.match_info['sessionId'])
        result = await get_old_session(user_id, session_id)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def delete_session(request):
    try:
        session_id = int(request.match_info['sessionId'])
        result = await delete_session_details(session_id)
        if not result:
            return web.json_response(
                {"error": "Session not found"}, status=404)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def clear_session(request):
    try:
        session_id = int(request.match_info['sessionId'])
        data = await request.json()
        result = await clear_conversation(session_id, data)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def update_session(request):
    try:
        session_id = int(request.match_info['sessionId'])
        data = await request.json()
        result = await update_session_details(session_id, data)
        payload = orjson.dumps(result).decode("utf-8")
        return web.json_response(payload)
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)