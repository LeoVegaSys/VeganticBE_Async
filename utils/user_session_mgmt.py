from managers.user_session_db.engine import UserSessionsManager


async def get_user_details(user_id : str):
    '''SELECT id, username, display_name FROM users WHERE id = ? LIMIT 1;'''
    pass


async def get_user_sessions(user_id: str):
    '''
    SELECT cs.id, cs.label, cs.networks, cs.levels, cs.circle, cs.services,
           cs.date_from, cs.date_to, cs.time_start, cs.time_end, cs.updated_at,
           (SELECT COUNT(*) FROM chat_messages cm WHERE cm.session_id = cs.id) AS message_count
    FROM chat_sessions cs
    WHERE cs.user_id = ?
    ORDER BY cs.id ASC;
    '''
    pass


async def get_next_section_label(user_id: str):
    '''SELECT COUNT(*) AS count FROM chat_sessions WHERE user_id = ?; 
    Return count + 1'''
    pass


async def add_new_session():
    '''INSERT INTO chat_sessions (
         user_id, label, networks, levels, circle, services,
         date_from, date_to, time_start, time_end
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);'''
    pass


async def get_old_session():
    '''
    1) Ownership verification:
       SELECT id FROM chat_sessions WHERE id = ? AND user_id = ? LIMIT 1;
    2) Fetch chronological messages:
       SELECT role, text, kind, rows_json, created_at
       FROM chat_messages
       WHERE session_id = ?
       ORDER BY id ASC;
    '''
    pass


async def update_session_filters():
    '''
    UPDATE chat_sessions
    SET networks = ?, levels = ?, circle = ?, services = ?,
        date_from = ?, date_to = ?, time_start = ?, time_end = ?
    WHERE id = ?;
  (If changing filters clears conversation):
    DELETE FROM chat_messages WHERE session_id = ?;
    DELETE FROM entity_tags WHERE session_id = ?;
    '''
    pass


async def clear_conversation():
    '''
    DELETE FROM chat_messages WHERE session_id = ?;
    DELETE FROM entity_tags WHERE session_id = ?;
    '''
    pass


async def delete_session():
    '''
    1) Ownership check:
       SELECT id FROM chat_sessions WHERE id = ? AND user_id = ? LIMIT 1;
    2) Delete session record:
       DELETE FROM chat_sessions WHERE id = ?;
       (Foreign keys with ON DELETE CASCADE automatically delete associated
        chat_messages and entity_tags rows)
    '''
    pass