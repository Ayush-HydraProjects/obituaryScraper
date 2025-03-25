import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL',
                                           'postgresql://postgres:admin@localhost/rememberingDB')
    SQLALCHEMY_TRACK_MODIFICATIONS = False