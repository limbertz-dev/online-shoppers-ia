"""Conexión a PostgreSQL con SQLAlchemy."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/online_shoppers')

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
