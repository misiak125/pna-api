from math import trunc
import os
from functools import wraps
from flask import request, jsonify
from src import db_session
from src.models import ApiKey, AppState
from datetime import datetime, date
from sqlalchemy import String, func, or_
import hashlib

def require_apikey(view_function):
    """
    Decorator validating api key against the database
    """
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        request_key = request.headers.get('X-API-Key')
        if not request_key:
            return jsonify({"error": "Missing API key in headers."}), 401

        hashed_request = hashlib.sha256(request_key.encode()).hexdigest()

        api_user = db_session.query(ApiKey).filter(ApiKey.key == hashed_request).first()

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
        update_sync_state(session)
        session.commit()
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


def short_price(price):
    if price is None:
        return ""
    try:
        price = float(price)
        if price % 1.0 == 0.0:
            return str(trunc(price))
        else:
            return f"{price:.2f}"
    except (ValueError, TypeError):
        return str(price)


def resource_path(relative_path):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# ==============================================================================
# AUDIT LOGGING
# ==============================================================================

def log_creation(instance, username: str):
    """
    Saves info about who created a product.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = username or "nieznany"
    instance.history = f"[{now_str}] Utworzono przez: {user}"


def log_modification(instance, username: str, column_name: str, old_value, new_value):
    """
    Updates rows history column about modification.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = username or "nieznany"
    
    # Format value for human-readable audit log
    def _format_val(v):
        if v is None:
            return "Brak"
        if isinstance(v, (datetime, date)):
            return v.strftime("%Y-%m-%d %H:%M:%S" if isinstance(v, datetime) and (v.hour or v.minute or v.second) else "%Y-%m-%d")
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    old_str = _format_val(old_value)
    entry = f"[{now_str}] Modyfikacja przez: {user} | Kolumna: {column_name} | Poprzednia wartość: {old_str}"
    
    current_history = (instance.history or "").strip()
    if current_history and current_history != "?":
        instance.history = f"{current_history}\n{entry}"
    else:
        instance.history = entry


def update_and_log(instance, updates: dict, username: str):
    """
    Updates object with dict attributes and logs it.
    """
    for col, new_val in updates.items():
        if not hasattr(instance, col):
            continue
        old_val = getattr(instance, col)
        
        # Compare with special handling for date and float types
        is_changed = False
        if old_val is None and new_val is not None and new_val != "":
            is_changed = True
        elif old_val is not None and new_val is None:
            is_changed = True
        elif old_val is not None and new_val is not None:
            if isinstance(old_val, float):
                try:
                    is_changed = (float(new_val) != old_val)
                except (ValueError, TypeError):
                    is_changed = (str(new_val) != str(old_val))
            elif isinstance(old_val, int) and not isinstance(old_val, bool):
                try:
                    is_changed = (int(new_val) != old_val)
                except (ValueError, TypeError):
                    is_changed = (str(new_val) != str(old_val))
            elif isinstance(old_val, datetime):
                # Normalise date
                new_dt = new_val
                if isinstance(new_val, str):
                    try:
                        new_dt = datetime.fromisoformat(new_val.replace("Z", "+00:00"))
                    except Exception:
                        try:
                            new_dt = datetime.strptime(new_val[:10], "%Y-%m-%d")
                        except Exception:
                            new_dt = new_val
                is_changed = (old_val != new_dt)
                new_val = new_dt
            else:
                is_changed = (str(old_val).strip() != str(new_val).strip())

        if is_changed:
            log_modification(instance, username, col, old_val, new_val)
            setattr(instance, col, new_val)
