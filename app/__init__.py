from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config.from_object(Config)
db = SQLAlchemy(app)

# Addition of login process
login = LoginManager(app)
login.login_view = 'login'

from app import routes, models, scrape