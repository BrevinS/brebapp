from flask import render_template, flash, redirect, url_for, request, Response
from flask_sqlalchemy import sqlalchemy
from app import app, db
from app.forms import RegisterForm, LoginForm, MLForm, MLFormS, KMeanForm, TextForm
from app.models import User, Dataframe, Feature, Tag
from flask_login import current_user, login_user, logout_user, login_required
import pandas as pd
import numpy as np
import sqlite3
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA  
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import datetime, time
import uuid
import cv2
import os
from config import basedir
import espn_scraper as espn
import json
from app.scrape import * 

@app.before_first_request
def initDB(*args, **kwargs):
    db.create_all()
    if Tag.query.count() == 0:
        tags = ['Target', 'Identifier', 'Feature']
        for t in tags:
            db.session.add(Tag(name=t))
        db.session.commit()

# https://stackoverflow.com/questions/68593071/timer-in-python-with-flask
@app.route('/content/<timers>') 
def content(timers):
    def timer(timers):
        # t will be the parameter we'll likely pass in
        # Subtract one second from timer datetime object
        # Make timers a datetime object
        print(timers)
        # Make timers PST
        timers = datetime.datetime.strptime(str(timers), "%Y-%m-%dT%H:%MZ")
       
        timers = timers - datetime.timedelta(seconds=1)
        
        time.sleep(1)
        yield str(timers)
    return Response(timer(timers), mimetype='text/html')

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

# A parameter in the future may be the gameId and that should be modular enough
@app.route('/nbalived', methods=['GET', 'POST'])
def nbalived():
    #json_data = espn.get_url("https://www.espn.com/nba/boxscore?gameId=401468968&_xhr=1")
    #team1, team2, stat_headers = athletes_scores_fromjson(json_data)
    #name1, name2, team1_stats, team2_stats, team_headers = team_stats_fromjson(json_data)
    now_games = upcoming_games()
    if request.method == 'GET':
        try:
            game_id = now_games[0][0]
            json_data = espn.get_url("https://www.espn.com/nba/boxscore?gameId=" + str(game_id) + "&_xhr=1")
            team1, team2, stat_headers = athletes_scores_fromjson(json_data)
            name1, name2, team1_stats, team2_stats, team_headers = team_stats_fromjson(json_data)
        except ValueError:
            print("WE HAVE A VALUE ERROR FROM GAME NOT STARTED")
            flash('No live games at this time')
            return render_template('nbalived.html')

    if request.method == 'POST':
        game_id = request.form['game_id']
        #print("This is the game id {}".format(game_id))
        json_data = espn.get_url("https://www.espn.com/nba/boxscore?gameId=" + str(game_id) + "&_xhr=1")
        
        try:
            team1, team2, stat_headers = athletes_scores_fromjson(json_data)
            name1, name2, team1_stats, team2_stats, team_headers = team_stats_fromjson(json_data)
        except KeyError:
            flash('Live boxscores for {} vs. {} unavailable at this time.'.format(name1, name2))
            print("WE HAVE A KEY ERROR FROM GAME NOT STARTED")
        
    return render_template('nbalived.html', team1=team1, team2=team2, stat_headers=stat_headers, 
                                            team1_stats=team1_stats, team2_stats=team2_stats,
                                            team1_name=name1, team2_name=name2, team_headers=team_headers, now_games=now_games)

@app.route('/prop/<player>', methods=['GET', 'POST'])
def prop(player):
    #remove white space from player name
    player = player.replace(" ", "")
    print(player)
    if request.method == 'GET':
        game_list, stat_list = props_today()
        # take the list of dictionaries stat_list and convert to a dataframe
        stat_list = pd.DataFrame(stat_list)
        # abbreviate each "name" to first name initial and last name
        stat_list['name'] = stat_list['name'].apply(lambda x: x.split()[0][0] + "." + x.split()[-1])
        print(stat_list)
        # find matching player name and team name in data frame and return the row
        
        stat_list = stat_list[(stat_list["name"] == player)]

        print(stat_list)

        # look up player under the "name" column inside the stat_list
        # if player is in stat_list, then return the player's stats
        if player in stat_list:
            player_stats = stat_list[stat_list['name'] == player]
            return render_template('prop.html', player_stats=player_stats, game_list=game_list)
    return render_template('about.html')

@app.route('/aboutme', methods=['GET', 'POST'])
def aboutme():
    #props_today()

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
            d = Dataframe(identifier=str(uuid.uuid4()), target=str(uuid.uuid4()))
            
            # Add all columns as featues (Tags must be used)
            for col in cf.columns:
                #print(col)
                f = Feature(feature_name=col)
                d.features.append(f)

            db.session.add(d)
            db.session.commit()

            return redirect(url_for('dataframeview', dataframe_id=d.id, option=0))
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

@app.route('/supervised/<dataframe_id>', methods=['GET', 'POST'])
def supervised(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)
    select = 0
    featurelist, identlist, targetlist = returnfeatures(dataf)

    print('Feature list {}'.format(featurelist))
    print('Identifier Vector {}'.format(identlist))
    print('Target list {}'.format(targetlist))

    # Put Features after identifier vector target at the end
    full = identlist + featurelist + targetlist
    
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

    form = MLFormS()
    if form.validate_on_submit():
        # select is the corresponding integer
        select = form.select.data
        print('FIRST TEXT {}'.format(select))
        # Must be Typecasted 
        if (int(select) == 1):
            return redirect(url_for('knn', dataframe_id=dataframe_id))
        elif (int(select) == 2):
            return redirect(url_for('hier', dataframe_id=dataframe_id))
        else:
            pass

    return render_template('supervised.html', featlist=featurelist, identlist=identlist, 
                targlist=targetlist, tables=[df.to_html(classes='data', header="true")], 
                columns=ac, choice=select, form=form)

@app.route('/knn/<dataframe_id>', methods=['GET', 'POST'])
def knn(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)

    featurelist, identlist, targetlist = returnfeatures(dataf)

    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('select * from dataframe', conn)
    y = df.loc[:, df.columns == '{}'.format(targetlist[0])]
    print('Target list {}'.format(y))
    ac = df.columns.values

    X = df.loc[:, df.columns != '{}'.format(targetlist[0])]
    print('KNN Dataset {}'.format(X))
    X = StandardScaler().fit_transform(X)
    X = pd.DataFrame(X)
    
    x_train, x_test, y_train, y_test = train_test_split(X, y, test_size = 0.2)
    model = KNeighborsClassifier(n_neighbors = 1)

    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)

    print(classification_report(y_test, y_pred))
    # I need a better dataset to got further... We can list the missfires and accuracies
    # KNN will need a recommended number of neighbors based on error rate. 

    rate = accuracy_score(y_test, y_pred)

    return render_template('knn.html', columns=ac, accuracy=float(rate), 
            tables=[df.to_html(classes='data', header="true")])

# Submit unsupervised dataset
@app.route('/unsupervised/<dataframe_id>', methods=['GET', 'POST'])
def unsupervised(dataframe_id):
    dataf = Dataframe.query.get(dataframe_id)
    select = 0
    featurelist, identlist, targetlist = returnfeatures(dataf)

    print('Feature list {}'.format(featurelist))
    print('Identifier Vector {}'.format(identlist))

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

    if request.args.get('nclusters'):
        print('NCLUSTERS')
        print(request.args.get('nclusters'))
        n = request.args.get('nclusters')
    if request.method == 'POST' and form.validate_on_submit():
        n = form.nclusters.data
        # EUCLIDEAN OR NOT?
        if(int(n) < 2):
            n = 3
        model = AgglomerativeClustering(n_clusters=int(n), affinity='euclidean', linkage='ward')
        X = df.loc[:, df.columns != '{}'.format(identlist[0])]
        try:
            X = StandardScaler().fit_transform(X)
            pca = PCA(n_components = int(len(featurelist)))
            X = pca.fit_transform(X)
            X = pd.DataFrame(X)
            model.fit(X.iloc[:,:2])
            labels = model.labels_
        
            X = X.iloc[:,:2]
            plt.ioff()
            fig = plt.figure()
            plt.scatter(X[0], X[1], c=labels, cmap='rainbow')

            if len(os.listdir('static/plts')) is not None:
                print('DIRECTORY EMPTY')
                if 'hier_pic.png' in os.listdir('static/plts'):
                    os.remove('static/plts/hier_pic.png')
                    print('Removed hier_pic.png')
            
            plt.savefig('static/plts/hier_pic.png')
            print('SAVING HIER PIC---------')
            plt.close(fig)

        except ValueError:
            flash('Features must contain ordinal values i.e. "1", "2", etc...')

    return render_template('hier.html', columns=ac, nclusters=n, clusterc=clustercenters, 
                tables=[df.to_html(classes='data', header="true")], form=form, dataframe_id=dataframe_id)

@app.route('/update/<dataframe_id>/<mlalg>/<ncluster>/<op>', methods=['GET', 'POST'])
def update(dataframe_id, mlalg, ncluster, op):
    dataf = Dataframe.query.get(dataframe_id)

    featurelist, identlist, targetlist = returnfeatures(dataf)

    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('select * from dataframe', conn)
    ac = df.columns.values

    clustercenters = []
    
    if(op == '1'):
        ncluster = int(ncluster) - 1
        if(ncluster < 2):
            if(mlalg == '1'):
                flash('K-Means must have at least 2 clusters')
                return redirect(url_for('kmeans', dataframe_id=dataframe_id))
            elif(mlalg == '2'):
                flash('Hierarchical Clustering must have at least 2 clusters')
                return redirect(url_for('hier', dataframe_id=dataframe_id))
    elif(op == '2'):
        ncluster = int(ncluster) + 1
    else:
        pass

    n = ncluster

    if(mlalg == '1'):
        model = KMeans(n_clusters=int(n))
        X = df.loc[:, df.columns != '{}'.format(identlist[0])]
    elif(mlalg == '2'):
        model = AgglomerativeClustering(n_clusters=int(n), affinity='euclidean', linkage='ward')
        X = df.loc[:, df.columns != '{}'.format(identlist[0])]

    print('Identity {}'.format(identlist))

    form = KMeanForm()
    try:
        X = StandardScaler().fit_transform(X)
        pca = PCA(n_components = int(len(featurelist)))
        X = pca.fit_transform(X)
        X = pd.DataFrame(X)
        #print('CLUSTER CENTERS')
        #print(model.cluster_centers_)
        #clustercenters = model.cluster_centers_
        model.fit(X.iloc[:,:2])
        labels = model.labels_
        X = X.iloc[:,:2]
        plt.ioff()
        fig = plt.figure()
        plt.scatter(X[0], X[1], c=labels, cmap='rainbow')

        if(mlalg == '1'):
            if 'kmean_pic.png' in os.listdir('static/plts'):
                os.remove('static/plts/kmean_pic.png')
                print('Removed kmean_pic.png')
            plt.savefig('static/plts/kmean_pic.png')
            plt.close(fig)
        elif(mlalg == '2'):
            if 'hier_pic.png' in os.listdir('static/plts'):
                os.remove('static/plts/hier_pic.png')
                print('Removed hier_pic.png')
            plt.savefig('static/plts/hier_pic.png')
            plt.close(fig)

    except ValueError:
            flash('Features must contain ordinal values i.e. "1", "2", etc...')
            # POSSIBLE REFER TO OTHER PAGE? ONEHOTENCODING,.. etc.
    
    if(mlalg == '1'):
        return redirect(url_for('kmeans', dataframe_id=dataframe_id, nclusters=n))
    elif(mlalg == '2'):
        return redirect(url_for('hier', dataframe_id=dataframe_id, nclusters=n))

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
    n = 2
    clustercenters = []

    if request.args.get('nclusters'):
        print('NCLUSTERS')
        print(request.args.get('nclusters'))
        n = request.args.get('nclusters')
    if request.method == 'POST' and form.validate_on_submit():
        #print current working directory
        n = form.nclusters.data
        if(int(n) < 2):
            n = 3
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
            plt.ioff()
            fig = plt.figure()
            #fig1 = plt.figure()
            #ax = fig1.add_subplot(111, projection='3d')
            #ax.scatter(X[0], X[1], X[2], c=labels, cmap='rainbow')

            plt.scatter(X[0], X[1], c=labels, cmap='rainbow')

            if 'kmean_pic.png' in os.listdir('static/plts'):
                os.remove('static/plts/kmean_pic.png')
                print('Removed kmean_pic.png')
            
            plt.savefig('static/plts/kmean_pic.png')
            plt.close(fig)

        except ValueError:
            flash('Features must contain ordinal values i.e. "1", "2", etc...')
            # POSSIBLE REFER TO OTHER PAGE? ONEHOTENCODING,.. etc.

    return render_template('kmeans.html', columns=ac, nclusters=n, clusterc=clustercenters, 
                tables=[df.to_html(classes='data', header="true")], form=form, dataframe_id=dataframe_id)

@app.route('/dataframeview/<dataframe_id>/<option>', methods=['GET', 'POST'])
def dataframeview(dataframe_id, option):
    conn = sqlite3.connect('dataframe.db')
    c = conn.cursor()
    df = pd.read_sql('select * from dataframe', conn)
    
    if request.method == 'POST':
        option = request.values.get("option")
        print('Option was {}'.format(str(option)))
        if option is not None:
            print('BIG TEST')
            option = int(option)

    # To reference in _features.html loop in dataframeview.html
    dataf = Dataframe.query.get(dataframe_id)
    feats = [] 
    idents = []
    ac = df.columns.values
    
    feats, idents, targs = returnfeatures(dataf)

    return render_template('dataframeview.html', option=int(option), 
                tables=[df.to_html(classes='data', header="true")],
                columns=ac, dataframe=dataf, dataframe_id=dataframe_id,
                featlist=feats, identlist=idents, targlist=targs, shape=df.shape)

# Add feature tag to given column in given dataframe
@app.route('/addfeature/<column_name>/<dataframe_id>/<option>', methods=['POST'])
def addfeature(column_name, dataframe_id, option):
    t = Tag(name="Feature")
    dataframe = Dataframe.query.get(dataframe_id)
    for feat in dataframe.features:
        if column_name == feat.feature_name:
            for r in feat.tags:
                feat.tags.remove(r)  
            print('Added feature - name: {} tag name: {}'.format(feat.feature_name, t.name))
            feat.tags.append(t)
    db.session.commit()

    return redirect(url_for('dataframeview', dataframe_id=dataframe.id, option=option))

# Add identifier tag to given column in given dataframe
@app.route('/addidentifier/<column_name>/<dataframe_id>/<option>', methods=['POST'])
def addidentifier(column_name, dataframe_id, option):
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
            #dataframe.identifier = column_name
            #print("New dataframe.identifier {}".format(dataframe.identifier))
    db.session.commit()

    return redirect(url_for('dataframeview', dataframe_id=dataframe.id, option=option))

# Add target vector tag to given column in given dataframe
@app.route('/addtarget/<column_name>/<dataframe_id>//<option>', methods=['POST'])
def addtarget(column_name, dataframe_id, option):
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
            #dataframe.target = column_name
            #print("New dataframe.identifier {}".format(dataframe.target))
    db.session.commit()

    return redirect(url_for('dataframeview', dataframe_id=dataframe.id, option=option))

global switch
switch = 1

# Found https://towardsdatascience.com/video-streaming-in-web-browsers-with-opencv-flask-93a38846fe00
def gen_frames():  
    #global camera
    while True:
        # Local camera
        
        #camera = cv2.VideoCapture(0) 
        success, frame = camera.read()  
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

#camera = cv2.VideoCapture(0)

#@app.route('/record', methods=['GET', 'POST'])
#def record():
#    global switch, camera
#    if request.method == 'POST':
#        if request.form.get('cap') == 'Capture':
#            pass
#        elif request.form.get('some') == 'Something':
#            pass
#        elif request.form.get('stop') == 'Stop/Start':
#            if(switch == 1):
#                switch = 0
#                camera.release()
#                cv2.destroyAllWindows()                
#            else:
#                camera = cv2.VideoCapture(0)
#                switch = 1    
#    elif request.method=='GET':
#        return render_template('record.html')
#    return render_template('record.html')

#@app.route('/livefeed', methods=['GET'])
#def livefeed():
#    time.sleep(5)
#    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

