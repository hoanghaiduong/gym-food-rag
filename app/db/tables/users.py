# app/db/tables/users.py
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime, Float, func
from app.db.base import metadata

users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50), unique=True, nullable=False),
    Column('email', String(100), unique=True, nullable=False),
    Column('password_hash', String(255), nullable=False),
    Column('full_name', String(100), nullable=True),
    Column('is_active', Boolean, default=True),
    Column('age', Integer, nullable=True),
    Column('gender', String(10), nullable=True),
    Column('weight', Float, nullable=True),
    Column('height', Float, nullable=True),
    Column('activity_level', String(20), nullable=True),
    Column('dietary_preference', String(50), nullable=True),
    Column('allergies', String(255), nullable=True),
    Column('target_goal', String(50), nullable=True),
    Column('refresh_token', String(500), nullable=True),
    Column('refresh_token_expires_at', DateTime, nullable=True),
    Column('created_at', DateTime, server_default=func.now())
)