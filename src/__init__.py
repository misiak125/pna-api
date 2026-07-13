import os
from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.exceptions import HTTPException
import traceback
from flask_status import FlaskStatus


app = Flask(__name__)
FlaskStatus(app)


""" ---------------------- logging configuration ------------------------- """
if not os.path.exists('logs'):
    os.mkdir('logs')

# saving logs to app.log (max 1MB oer file, max 10 old files)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)

app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Starting server API PNA')

@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    """
    Global unhandled errors logger.
    """
    if isinstance(e, HTTPException):
        return e

    
    app.logger.exception("[CRITICAL] Unhandled Exception:")
    
    
    return jsonify({
        "error": "Wystąpił nieoczekiwany błąd serwera."
    }), 500


""" ------------------ blocking http connection -----------------------------"""
@app.before_request
def enforce_https():
    """
    Blokuje każde żądanie, które nie przyszło przez HTTPS.
    """
    if request.host.startswith('localhost') or request.host.startswith('127.0.0.1'):
        return None

    proto = request.headers.get('X-Forwarded-Proto', request.scheme)
    if proto.lower() != 'https':
        return jsonify({"error": "Nieszyfrowane połączenia (HTTP) są zablokowane. Użyj HTTPS."}), 403


""" ---------------------- limits configuration ------------------------- """
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["500 per day", "60 per minute"], 
    storage_uri="memory://"
)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "Rate Limit exceeded.", 
        "details": str(e.description)
    }), 429


""" ---------------------- DB configuration ------------------------- """
load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("DATABASE_URL not in .env")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
Base = declarative_base()

from src.models import Product, Customer, Reservation, Brand, Model, Colour, AppState, ApiKey

Base.metadata.create_all(bind=engine)



SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db_session = scoped_session(SessionMaker)



@app.teardown_appcontext
def shutdown_session(exception=None):
    """Automatic session closer"""
    db_session.remove()