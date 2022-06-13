from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, current_user

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

#Relationships
coltags = db.Table('coltags',
    db.Column('df_id', db.Integer, db.ForeignKey('dataframe.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
    )

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True)
    password_hash = db.Column(db.String(128))
    firstname = db.Column(db.String(64))
    lastname = db.Column(db.String(64))
    email = db.Column(db.String(120), index=True, unique=True)

    def get_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Dataframe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(100), unique=False)
    features = db.Column(db.String(2000), unique=False)

    tags = db.relationship('Tag', secondary=coltags,
                            primaryjoin=(coltags.c.df_id == id),
                            backref=db.backref('coltags', lazy='dynamic'), lazy='dynamic')

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    
    courses = db.relationship('Dataframe', secondary=coltags,
                               primaryjoin=(coltags.c.tag_id == id),
                               backref=db.backref('coltags', lazy='dynamic'),
                               lazy='dynamic')




