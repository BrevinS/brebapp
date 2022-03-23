from flask import render_template, flash, redirect, url_for, request
from app import app, db
from flask_sqlalchemy import sqlalchemy
from app.forms import RegisterForm
from app.models import User
from flask_login import current_user, login_user, logout_user, login_required

@app.before_first_request
def initDB(*args, **kwargs):
    db.create_all()

@app.route('/', methods=['GET'])
@app.route('/index', methods=['GET'])
def index():
    form = RegisterForm()
    if form.validate_on_submit():
        acc = User(username=form.username.data, email=form.email.data, firstname=form.firstname.data,
            lastname=form.lastname.data)
        acc.get_password(form.password2.data)
        db.session.add(acc)
        db.session.commit()
        flash('Congrats you have created an account!')
        ##REDIRECT AFTER STUDENT REGISTERS THEY NEED TO SEE COURSES && APPLY
        ##I need to add new page
        return redirect(url_for('index'))
    return render_template('user_registration.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        acc = User(username=form.username.data, email=form.email.data, firstname=form.firstname.data,
            lastname=form.lastname.data)
        acc.get_password(form.password2.data)
        db.session.add(acc)
        db.session.commit()
        flash('Congrats you have created an account!')
        ##REDIRECT AFTER STUDENT REGISTERS THEY NEED TO SEE COURSES && APPLY
        ##I need to add new page
        return redirect(url_for('index'))
    return render_template('user_registration.html', title='Register', form=form)
