from flask import render_template, flash, redirect, url_for, request
from app import app, db
from flask_sqlalchemy import sqlalchemy
from app.forms import RegisterForm, LoginForm
from app.models import User
from flask_login import current_user, login_user, logout_user, login_required

@app.before_first_request
def initDB(*args, **kwargs):
    db.create_all()

@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
def index():
    return render_template('base.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        acc = User(username=form.username.data, email=form.email.data, firstname=form.firstname.data,
            lastname=form.lastname.data)
        acc.get_password(form.password2.data)
        db.session.add(acc)
        db.session.commit()
        login_user(acc)
        flash('Congrats you have registered')
        return redirect(url_for('index'))
    return render_template('user_registration.html', form=form)

@login_required
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        student = User.query.filter_by(username=form.username.data).first()
        if student is None or not student.check_password(form.password.data):
            flash('Not a username or incorrect password!')
            return redirect(url_for('login'))
        login_user(student, remember=form.rememberme.data)
        return redirect(url_for('index'))
    return render_template('login.html', title='Login Page', form=form)

@app.route('/aboutme', methods=['GET', 'POST'])
def aboutme():
    return render_template('about.html')

