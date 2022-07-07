from flask import render_template, flash, redirect, url_for, request
from flask_sqlalchemy import sqlalchemy
from app import app, db
from app.forms import RegisterForm, LoginForm, MLForm, KMeanForm
from app.models import User, Dataframe, Feature, Tag
from flask_login import current_user, login_user, logout_user, login_required
import pandas as pd
import sqlite3
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA  
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

@app.before_first_request
def initDB(*args, **kwargs):
    db.create_all()
    if Tag.query.count() == 0:
        tags = ['Target', 'Identifier', 'Feature']
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
        return redirect(url_for('homepage'))
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
            cf = df
            print("Shape of df {}".format(df.shape))


            conn = sqlite3.connect('dataframe.db')
            c = conn.cursor()
            # Don't append - WE CAN TUPLE With current_user.id? 
            df.to_sql('dataframe', conn, if_exists='replace', index = False)
            conn.commit()

            p = pd.read_sql('select * from dataframe', conn)
            print('Dataframe {}'.format(p))
            conn.close()

            # Initialize Dataframe
            d = Dataframe(identifier="nothing", target="alsonothing")
            
            # Add all columns as featues (Tags must be used)
            for col in cf.columns:
                #print(col)
                f = Feature(feature_name=col)
                d.features.append(f)

            db.session.add(d)
            db.session.commit()

            return redirect(url_for('dataframeview', dataframe_id=d.id))
        else:
            flash('FILE MUST BE OF TYPE .csv')
    return render_template('homepage.html')

# Takes in python list of headers for SELECT {} FROM database.db
def sqlite3string(headers):
    new = []
    for string in headers:
        # Add quotes around headers with a space in it
        if " " in string:
            new.append("\"" + string + "\"")
        else:
            new.append(string)
    refull = str(new)
    # Refactor into a SQLITE Query-able string, this looks bad but works
    # Remove ' from whole string
    refull = refull.replace('\'', "")
    # Remove [ and ] from the beginning and end of string
    refull = refull[1:-1]

    return refull

# TAKES IN dataframe (pandas)
def returnfeatures(df):
    featurelist = []
    identlist = [] 
    targetlist = []
    for feat in df.features:
        for t in feat.tags:
            if t.name == 'Feature':
                featurelist.append(feat.feature_name)
            elif t.name == 'Identifier':
                identlist.append(feat.feature_name)
            elif t.name == 'Target':
                targetlist.append(feat.feature_name)
    
    return featurelist, identlist, targetlist

# Submit unsupervised dataset
@app.route('/unsupervised/<dataframe_id>', methods=['GET', 'POST'])
def unsupervised(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)
    select = 0
    featurelist, identlist, targetlist = returnfeatures(dataf)
    
    print('Feature list {}'.format(featurelist))
    print('Identifier Vector {}'.format(identlist))
    print('Target list {}'.format(targetlist))

    # Put Features after identifier vector
    full = identlist + featurelist
    
    # Python list of headers to SQlite3 
    querylang = sqlite3string(full)

    # Now I need Query database.db for featurelist with identlist at the start
    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('SELECT {} FROM dataframe'.format(querylang), conn)
    df.to_sql('dataframe', conn, if_exists='replace', index = False)
    conn.commit()
    conn.close()

    ac = df.columns.values

    form = MLForm()
    if form.validate_on_submit():
        # select is the corresponding integer
        select = form.select.data
        print('FIRST TEXT {}'.format(select))
        # Must be Typecasted 
        if (int(select) == 1):
            return redirect(url_for('kmeans', dataframe_id=dataframe_id))
        elif (int(select) == 2):
            return redirect(url_for('hier', dataframe_id=dataframe_id))
        else:
            pass

    return render_template('unsupervised.html', featlist=featurelist, identlist=identlist, 
                targlist=targetlist, tables=[df.to_html(classes='data', header="true")], 
                columns=ac, choice=select, form=form)

@app.route('/hier/<dataframe_id>', methods=['GET', 'POST'])
def hier(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)

    featurelist, identlist, targetlist = returnfeatures(dataf)

    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('select * from dataframe', conn)
    ac = df.columns.values

    form = KMeanForm()
    n = 0
    clustercenters = []
    if request.method == 'POST' and form.validate_on_submit():
        n = form.nclusters.data
        # EUCLIDEAN OR NOT?
        model = AgglomerativeClustering(n_clusters=int(n), affinity='euclidean', linkage='ward')
        X = df.loc[:, df.columns != '{}'.format(identlist[0])]
        try:
            X = StandardScaler().fit_transform(X)
            pca = PCA(n_components = int(len(featurelist)))
            X = pca.fit_transform(X)
            X = pd.DataFrame(X)
            model.fit(X.iloc[:,:2])
            labels = model.labels_

            #for a in set(labels):
            #    y = df[[labels]==a].mean(axis=0)
            #    clustercenters.append(list(y[:-1]))
            
            X = X.iloc[:,:2]
            #plt.scatter(X[0], X[1], c=labels, cmap='rainbow')
            #plt.savefig('hier_pic.png')
        except ValueError:
            flash('Features must contain ordinal values i.e. "1", "2", etc...')

    return render_template('hier.html', columns=ac, nclusters=n, clusterc=clustercenters, 
                tables=[df.to_html(classes='data', header="true")], form=form)

# KMEANS template. Show something relevant
# STILL NEEDS: Graph, Elbow #Clusters recommendation, plt.scatter sucks
@app.route('/kmeans/<dataframe_id>', methods=['GET', 'POST'])
def kmeans(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)

    featurelist, identlist, targetlist = returnfeatures(dataf)

    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('select * from dataframe', conn)
    ac = df.columns.values

    # What more do we want? # of clusters?
    form = KMeanForm()
    n = 0
    clustercenters = []
    if request.method == 'POST' and form.validate_on_submit():
        n = form.nclusters.data
        model = KMeans(n_clusters=int(n))
        #flash('Number of Clusters! {}'.format(int(n)))
        print('Identity {}'.format(identlist))
        X = df.loc[:, df.columns != '{}'.format(identlist[0])]
        try:
            X = StandardScaler().fit_transform(X)
            pca = PCA(n_components = int(len(featurelist)))
            X = pca.fit_transform(X)
            X = pd.DataFrame(X)
            model.fit(X.iloc[:,:2])
            print('CLUSTER CENTERS')
            print(model.cluster_centers_)
            clustercenters = model.cluster_centers_
            labels = model.predict(X.iloc[:,:2])
            #plt.scatter(X[0], X[1], c=labels, cmap='rainbow')
            #plt.savefig('kmean_pic.png')
        except ValueError:
            flash('Features must contain ordinal values i.e. "1", "2", etc...')

    return render_template('kmeans.html', columns=ac, nclusters=n, clusterc=clustercenters, 
                tables=[df.to_html(classes='data', header="true")], form=form)

@app.route('/dataframeview/<dataframe_id>', methods=['GET'])
def dataframeview(dataframe_id):
    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('select * from dataframe', conn)

    # To reference in _features.html loop in dataframeview.html
    dataf = Dataframe.query.get(dataframe_id)
    feats = []
    idents = []
    ac = df.columns.values
    
    feats, idents, targs = returnfeatures(dataf)

    return render_template('dataframeview.html', tables=[df.to_html(classes='data', header="true")],
                columns=ac, dataframe=dataf, dataframe_id=dataframe_id,
                featlist=feats, identlist=idents, targlist=targs, shape=df.shape)

# Add feature tag to given column in given dataframe
@app.route('/addfeature/<column_name>/<dataframe_id>', methods=['POST'])
def addfeature(column_name, dataframe_id):
    t = Tag(name="Feature")
    dataframe = Dataframe.query.get(dataframe_id)
    for feat in dataframe.features:
        if column_name == feat.feature_name:
            for r in feat.tags:
                feat.tags.remove(r)  
            print('Added feature - name: {} tag name: {}'.format(feat.feature_name, t.name))
            feat.tags.append(t)
    db.session.commit()

    return redirect(url_for('dataframeview', dataframe_id=dataframe.id))

# Add identifier tag to given column in given dataframe
@app.route('/addidentifier/<column_name>/<dataframe_id>', methods=['POST'])
def addidentifier(column_name, dataframe_id):
    t = Tag(name="Identifier")
    dataframe = Dataframe.query.get(dataframe_id)
    for feat in dataframe.features:
        # Reset all identifiers?
        for f in feat.tags:
            if f.name == 'Identifier':
                feat.tags.remove(f)
        if column_name == feat.feature_name:
            for r in feat.tags:
                feat.tags.remove(r)    
            print('Added identifier - name: {} tag name: {}'.format(feat.feature_name, t.name))
            feat.tags.append(t)
            dataframe.identifier = column_name
            print("New dataframe.identifier {}".format(dataframe.identifier))
    db.session.commit()

    return redirect(url_for('dataframeview', dataframe_id=dataframe.id))

# Add target vector tag to given column in given dataframe
@app.route('/addtarget/<column_name>/<dataframe_id>', methods=['POST'])
def addtarget(column_name, dataframe_id):
    t = Tag(name="Target")
    dataframe = Dataframe.query.get(dataframe_id)
    for feat in dataframe.features:
        # Reset all identifiers?
        for f in feat.tags:
            if f.name == 'Target':
                feat.tags.remove(f)
        if column_name == feat.feature_name:
            for r in feat.tags:
                feat.tags.remove(r)    
            print('Added identifier - name: {} tag name: {}'.format(feat.feature_name, t.name))
            feat.tags.append(t)
            dataframe.target = column_name
            print("New dataframe.identifier {}".format(dataframe.target))
    db.session.commit()

    return redirect(url_for('dataframeview', dataframe_id=dataframe.id))




# USELESS 
@app.route('/unsuperanalysis/<dataframe_id>', methods=['GET', 'POST'])
def unsuperanalysis(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)

    featurelist, identlist = returnfeatures(dataf)

    if request.method == 'POST':
        alg = request.values.get("algorithm")
        print('Algorithm is {}'.format(alg))
    
    return render_template('unsuperanalysis.html', dataframe_id=dataframe_id)