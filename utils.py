import os
from functools import wraps
from flask import request, jsonify


def require_apikey(view_function):
    """
    Decorator validating api key passed as "X-API-Key"
    """
    VALID_API_KEYS = os.getenv("VALID_API_KEYS")
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        request_key = request.headers.get('X-API-Key')

        if request_key and request_key in VALID_API_KEYS:
            request.current_user = VALID_API_KEYS[request_key]
            return view_function(*args, **kwargs)
        else:
            return jsonify({"error": "Nieautoryzowany dostęp. Błędny lub brakujący klucz API."}), 401

    return decorated_function


def update_sync_state(session):
    try:
        state = session.query(AppState).first()
        if not state:
            state = AppState(last_update=datetime.now())
            session.add(state)
        else:
            state.last_update = datetime.now()
    except:
        raise


def commit_update(session):
    """
    Commits to db and updates last changes state.
    """
    try:
        update_sync_state(db_session)
        commit_update(db_session)
    except:
        raise


def apply_search_filters(query, search_string: str, columns: list):
    """
    Edits query by adding a requirement for every word form 
    search_string to appear in any column.
    """
    if not search_string:
        return query
    
    words = search_string.strip().split()
    for word in words:
        search_term = f"%{word}%"
        or_conditions = [func.cast(col, String).ilike(search_term) for col in columns]
        query = query.filter(or_(*or_conditions))
    return query