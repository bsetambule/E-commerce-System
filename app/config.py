import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key"

    # MySQL connection
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@127.0.0.1:3307/shop"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # app/config.py
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app/static/uploads')
   
    BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")

    FRONTEND_URL = "http://127.0.0.1:5000"
