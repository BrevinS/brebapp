from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField, IntegerField, PasswordField, SelectField, BooleanField
from wtforms.validators import ValidationError, Length, DataRequired, Email, EqualTo
from app.models import User, Tag

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password1 = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), 
                EqualTo('password1')])
    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        _user = User.query.filter_by(username=username.data).first()
        if _user is not None:
            raise ValidationError('Username already exists! Try another...')
            
    def validate_email(self, email):
        _user = User.query.filter_by(email=email.data).first()
        if _user is not None:
            raise ValidationError('Email has already been used! Try another...')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    rememberme = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

def get_tag():
    return Tag.query
    