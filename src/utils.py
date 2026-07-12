import os
from functools import wraps
from flask import request, jsonify
from src import db_session
from src.models import ApiKey

def require_apikey(view_function):
    """
    Decorator validating api key against the database
    """
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        request_key = request.headers.get('X-API-Key')

        if not request_key:
            return jsonify({"error": "Missing API key in headers."}), 401

        api_user = db_session.query(ApiKey).filter(ApiKey.key == request_key).first()

        if api_user:
            request.current_user = api_user.username
            return view_function(*args, **kwargs)
        else:
            return jsonify({"error": "Unauthorised access. Wrong API key."}), 401

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


def db_commit_update(session):
    """
    Commits to db and updates last changes state.
    """
    try:
        update_sync_state(db_session)
        db_session.commit()
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