from utils.context import (
    DeleteSessionRequest, ClearSessionRequest, NewSessionRequest,
    UpdateSessionRequest, UserDetailsRequest, UserSessionsRequest)
from managers.user_session_db.engine import UserSessionsManager
from config.user_sessions import DEL_SESS_ON_FILTER_CHANGE


async def get_user_details(data: dict):
    try:
        obj = UserDetailsRequest(body=data)
        query = f'SELECT id, username, display_name FROM users WHERE id = {obj.user_id} LIMIT 1;'
        result = await UserSessionsManager().aget(query)
        return result["rows"]
    except Exception as e:
        raise e


async def get_user_sessions(data: dict):
    try:
        obj = UserSessionsRequest(body=data)
        query = f'''SELECT cs.id, cs.label, cs.networks, cs.levels, cs.circle, cs.services,
                   cs.date_from, cs.date_to, cs.time_start, cs.time_end, cs.updated_at,
                   (SELECT COUNT(*) FROM chat_messages cm WHERE cm.session_id = cs.id) AS message_count
            FROM chat_sessions cs
            WHERE cs.user_id = {obj.user_id}
            ORDER BY cs.id ASC;'''
        result = await UserSessionsManager().aget(query)
        return result["rows"]
    except Exception as e:
        raise e


async def get_next_section_label(user_id: int):
    '''SELECT COUNT(*) AS count FROM chat_sessions WHERE user_id = ?; 
    Return count + 1'''
    try:
        query = f'SELECT COUNT(*) AS count FROM chat_sessions WHERE user_id = {user_id};'
        result = await UserSessionsManager().aget(query)
        return int(result["rows"][0]["count"]) + 1
    except Exception as e:
        raise e


async def create_new_session(data: dict):
    try:
        obj = NewSessionRequest(body=data)
        next_label_id = await get_next_section_label(obj.user_id)
        next_label = f'{obj.label} {next_label_id}'
        query = f'''
        INSERT INTO chat_sessions (
            user_id, label, networks, levels, circle, services,
            date_from, date_to, time_start, time_end
        ) VALUES (
            {obj.user_id}, {next_label}, {obj.networks}, {obj.levels},
            {obj.circle}, {obj.services}, {obj.date_from},
            {obj.date_to}, {obj.time_from}, {obj.time_to}
            );'''
        res = await UserSessionsManager().ainsert([query])
        new_session_id = int(res['new_id'])
        query_2 = f'''SELECT * from chat_sessions where id = {new_session_id};'''
        result = await UserSessionsManager().aget(query_2)
        # Get latest created session details and return
        return result
    except Exception as e:
        raise e


async def add_new_user(data:dict):
    try:
        query = f'''
        INSERT INTO users (
            username, password_hash, display_name) VALUES (
            {data['uname']}, {data['pwd']}, {data['udisp']});'''
        result = await UserSessionsManager().ainsert([query])
        return result
    except Exception as e:
            raise e


async def get_old_session(user_id: int, session_id: int):
    '''
    1) Ownership verification:
       SELECT id FROM chat_sessions WHERE id = ? AND user_id = ? LIMIT 1;
    2) Fetch chronological messages:
       SELECT role, text, kind, rows_json, created_at
       FROM chat_messages
       WHERE session_id = ?
       ORDER BY id ASC;
    '''
    try:
        # Ownership verification
        query_1 = f'''
            SELECT id FROM chat_sessions
            WHERE id = {session_id} AND user_id = {user_id}
            LIMIT 1;'''
        exists = await UserSessionsManager().aget(query_1)
        if exists["rowCount"] > 0:
            # Fetch chronological messages
            query_2 = f'''
                SELECT role, text, kind, rows_json, created_at
                FROM chat_messages
                WHERE session_id = {session_id}
                ORDER BY id ASC;'''
            result = await UserSessionsManager().aget(query_1)
            return result["rows"]
        return []
    except Exception as e:
        raise e


async def update_session_details(session_id : int, data: dict):
    try:
        obj = UpdateSessionRequest(body=data)
        query_1 = f'''
            UPDATE chat_sessions
            SET networks = {obj.networks}, levels = {obj.levels},
                circle = {obj.circle}, services = {obj.services},
                date_from = {obj.date_from}, date_to = {obj.date_to},
                time_start = {obj.time_from}, time_end = {obj.time_to}
            WHERE id = {session_id};'''
        query_2 = f'DELETE FROM chat_messages WHERE session_id = {session_id};'
        query_3 = f'DELETE FROM entity_tags WHERE session_id = {session_id};'

        queries = [query_1, query_2, query_3] if DEL_SESS_ON_FILTER_CHANGE \
            else [query_1]
        result = await UserSessionsManager().aupd_del(queries)
        return result
    except Exception as e:
        raise e


async def clear_conversation(session_id: int, data: dict):
    try:
        obj = ClearSessionRequest(body=data)
        # What is the scope of clear_messages
        query_1 = f"DELETE FROM chat_messages WHERE session_id = {session_id};"
        query_2 = f"DELETE FROM entity_tags WHERE session_id = {session_id};"
        queries = [query_1, query_2]
        result = await UserSessionsManager().aupd_del(queries)
        return result
    except Exception as e:
        raise e


async def delete_session_details(session_id: int, data: dict):
    '''
    1) Ownership check:
       SELECT id FROM chat_sessions WHERE id = ? AND user_id = ? LIMIT 1;
    2) Delete session record:
       DELETE FROM chat_sessions WHERE id = ?;
       (Foreign keys with ON DELETE CASCADE automatically delete associated
        chat_messages and entity_tags rows)
    '''
    try:
        obj = DeleteSessionRequest(body=data)
        query_1 = f'''
        SELECT id FROM chat_sessions
        WHERE id = {session_id} AND user_id = {obj.user_id}
        LIMIT 1;'''
        query_2 = f'DELETE FROM chat_sessions WHERE id = {session_id};'
        dbm = UserSessionsManager()
        exists = await dbm.aget(query_1)
        if exists["rowCount"] > 0:
            result = await dbm.aupd_del([query_2])
            return result
        return {'ok': False}
    except Exception as e:
        raise e