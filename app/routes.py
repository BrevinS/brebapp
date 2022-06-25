from flask import render_template, flash, redirect, url_for, request
from app import app, db
from flask_sqlalchemy import sqlalchemy
from app.forms import RegisterForm, LoginForm, FeatureForm
from app.models import User, Dataframe, Feature,Tag
from flask_login import current_user, login_user, logout_user, login_required
import pandas as pd
import sqlite3

@app.before_first_request
def initDB(*args, **kwargs):
    db.create_all()
    if Tag.query.count() == 0:
        tags = ['Identifier', 'Feature']
        for t in tags:
            db.session.add(Tag(name=t))
        db.session.commit()

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

EXTENSION_ALLOWED = set(['csv'])

# https://www.middlewareinventory.com/blog/flask-app-upload-file-save-filesystem/
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in EXTENSION_ALLOWED

# Actual cool stuff going on now
@app.route('/homepage', methods=['GET', 'POST'])
@login_required
def homepage():
    if request.method == 'POST':
        data = request.files['file']
        if data and allowed_file(data.filename):
            df = pd.read_csv(request.files.get('file'))

            print("Shape of df {}".format(df.shape))

            conn = sqlite3.connect('dataframe.db')
            c = conn.cursor()
            # Don't append
            df.to_sql('dataframe', conn, if_exists='replace', index = False)
            conn.commit()

            p = pd.read_sql('select * from dataframe', conn)
            print('Dataframe {}'.format(p))
            conn.close()

            dataf = Dataframe(identifier="tester")
            db.session.add(dataf)
            db.session.commit()
            # Move data to feature selection
            #return redirect(url_for('dataframe', tables=[df.to_html(classes='data', header="true")],
            #    columns=df.columns.values, dataframe_id=dataf.id))
            
            return render_template('dataframe.html', 
                tables=[df.to_html(classes='data', header="true")],
                columns=df.columns.values, dataframe_id=dataf.id, dataframe=dataf)
            
            #return render_template('homepage.html', shape=df.shape, 
            #    tables=[df.to_html(classes='data', header="true")], 
            #    columns=df.columns.values, feats=[])
        else:
            flash('FILE MUST BE OF TYPE .csv')
    return render_template('homepage.html')

@app.route('/dataframe/<dataframe_id>', methods=['GET', 'POST'])
def dataframe(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)
    if request.method == 'POST':
        feature = Feature(feature_name=request.form['Feat'], Dataframe=dataf)
        db.session.add(feature)
        db.session.commit()
        return redirect(url_for('dataframe', dataframe_id=dataf.id))
    
    return redirect('dataframe', dataframe_id=dataf.id)

@app.route('/identify/<column>', methods=['GET', 'POST'])
def identify(column):
    if column:
        # They actually clicked something
        column = Dataframe(identifier=column)
        db.session.add(column)
        db.session.commit()
        flash("Selected For Identifier{}".format(column))
        redirect(url_for('homepage'))
        #return redirect(url_for('homepage.html'))
    #form = FeatureForm()
    #if form.validate_on_submit():
    #    return redirect(url_for('index'))
    #return render_template('homepage.html')

@app.route('/feature/<column>', methods=['GET', 'POST'])
def feature(column):
    #if column:
        # They actually clicked something
    #    flash("Selected For Feature{}".format(column))
        #return redirect(url_for('homepage'))
    form = FeatureForm()
    if form.validate_on_submit():
        return redirect(url_for('index'))
    return render_template('homepage.html')




