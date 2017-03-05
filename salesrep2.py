from flask import Flask, render_template, request, redirect, jsonify
from flask import url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from salesrep2_database import Base, SalesReps, RepDetails, User
from flask import session as login_session  # needed for oauth
import random  # needed for oauth
import string  # needed for oauth
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(open('client_secrets.json', 'r')
                       .read())['web']['client_id']
APPLICATION_NAME = 'salesreps python project'

# Connect to Database and create database session

engine = create_engine('sqlite:///salesreptwo.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# client ID:
# 353588693515-3441mau5vnq11kvco9kmnhk9o7lg2bc5.apps.googleusercontent.com
# client secret lUqBbBB-BfSe4IMPinOeNqor
# create a state token to prevent request fraud
# store it in the session for later validation

@app.route('/login')
def showLogin():

    # from class video on create Google sign-in

    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

    # "The current session state is %s" % login_session['state']


@app.route('/gconnect', methods=['POST'])
def gconnect():

    # Validate state token

    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Obtain authorization code

    code = request.data

    try:

        # Upgrade the authorization code into a credentials object

        oauth_flow = flow_from_clientsecrets('client_secrets.json',
                                             scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = \
            make_response(json.dumps('Failed to upgrade the authorization\
             code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.

    access_token = credentials.access_token
    login_session['access_token'] = access_token
    print login_session['access_token']
    url = \
        'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' \
        % access_token
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1].decode("utf8"))

    # If there was an error in the access token info, abort.

    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.

    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = \
            make_response(json.dumps("Token's user ID doesn't match\
             given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.

    if result['issued_to'] != CLIENT_ID:
        response = \
            make_response(json.dumps("Token's client ID does not match\
             app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = \
            make_response(json.dumps('Current user is already \
                connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.

    login_session['credentials'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info

    userinfo_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists....if not, make a new one

    user_id = getUserID(data['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['email']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += \
        ' " style = "width: 300px; height: 300px;border-radius:\
     150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash('you are now logged in as %s' % login_session['email'])
    print 'done!'
    return output


# helper functions to determine if user authorized to make changes
# creates new user in database with info gathered from login session
# returns ID of new user created

def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


# if user_id is passed in it returns user which was queried

def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).first()
    return user


# returns either user id if email belongs to user in database or None

def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# DISCONNECT - Revoke a current user's token and reset their login_session


@app.route('/gdisconnect')
def gdisconnect():
    try:
        print login_session.keys()
        access_token = login_session['access_token']
        print 'In gdisconnect access token is %s', access_token
        print 'User name is: '
        print login_session['email']
        if access_token is None:
            print 'Access Token is None'
            response = \
                make_response(json.dumps('Current user not connected.'), 401)
            response.headers['Content-Type'] = 'application/json'
            return response
        url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
            % login_session['access_token']
        h = httplib2.Http()
        result = h.request(url, 'GET')[0]
        print 'result is '
        print result
        if result['status'] == '200':
            del login_session['access_token']
            del login_session['gplus_id']
            del login_session['username']
            del login_session['email']
            del login_session['picture']
            response = \
                make_response(json.dumps('Successfully disconnected.'),
                              200)
            response.headers['Content-Type'] = 'application/json'
            return response
        else:

            response = \
                make_response(json.dumps('Failed to revoke token for \
                    given user.', 400))
            response.headers['Content-Type'] = 'application/json'
            return response
    except:
        return redirect(url_for('showLogin'))


# JSON APIs to view Salesrep and detail info

@app.route('/salesreps/repdetails/JSON')
def salesRepDetailsJSON():
    details = session.query(RepDetails).order_by(RepDetails.name).all()
    return jsonify(details=[i.serialize for i in details])


# JSON for single salesrep and details

@app.route('/salesreps/<int:salesrep_id>/repdetails/JSON')
def detailsJSON(salesrep_id):
    details = session.query(RepDetails).filter_by(id=salesrep_id).one()
    return jsonify(details=details.serialize)


# JSON--not sure if this is needed but for rep name only

@app.route('/salesreps/JSON')
def salesRepsJSON():
    salesreps = session.query(SalesReps).order_by(SalesReps.name)
    return jsonify(salesreps=[i.serialize for i in salesreps])


# Show all salesreps

@app.route('/')
@app.route('/salesreps/')
def showSalesReps():
    salesreps = session.query(SalesReps).order_by(asc(SalesReps.name))
    if 'username' not in login_session:
        return render_template('publicsalesreps.html',
                               salesreps=salesreps)
    else:
        return render_template('salesreps.html', salesreps=salesreps)


# Create a new sales rep

@app.route('/salesreps/new/', methods=['GET', 'POST'])
def newSalesReps():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newSalesRep = SalesReps(name=request.form['name'],
                                user_id=login_session['user_id'])
        session.add(newSalesRep)
        flash('New Sales Representative %s Successfully Created'
              % newSalesRep.name)
        session.commit()
        return redirect(url_for('showSalesReps'))
    else:
        return render_template('newSalesReps.html')


# Edit a sales rep

@app.route('/salesreps/<int:salesrep_id>/edit/', methods=['GET', 'POST'])
def editSalesRep(salesrep_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedSalesRep = \
        session.query(SalesReps).filter_by(id=salesrep_id).one()
    if editedSalesRep.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized \
        to edit this SalesRep.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedSalesRep.name = request.form['name']
            flash('Sales Representative Successfully Edited %s'
                  % editedSalesRep.name)
            return redirect(url_for('showSalesReps'))
    else:
        return render_template('editSalesReps.html',
                               salesrep=editedSalesRep)


# Delete a salesrep

@app.route('/salesreps/<int:salesrep_id>/delete/', methods=['GET',
           'POST'])
def deleteSalesRep(salesrep_id):
    if 'username' not in login_session:
        return redirect('/login')
    repToDelete = \
        session.query(SalesReps).filter_by(id=salesrep_id).one()
    if repToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized \
        to delete this SalesRep.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(repToDelete)
        flash('%s Successfully Deleted' % repToDelete.name)
        session.commit()
        return redirect(url_for('showSalesReps',
                        salesrep_id=salesrep_id))
    else:
        return render_template('deleteSalesRep.html',
                               salesrep=repToDelete)


# Show sales rep details for selected sales rep

@app.route('/salesreps/<int:salesrep_id>/')
@app.route('/salesreps/<int:salesrep_id>/repdetails')
def showRep(salesrep_id):
    salesrep = session.query(SalesReps).filter_by(id=salesrep_id).first()
    creator = getUserInfo(salesrep.user_id)
    details = \
        session.query(RepDetails).filter_by(salesrep_id=salesrep_id)
    if 'username' not in login_session:
        return render_template('publicrepdetails.html',
                               salesrep=salesrep, details=details)
    else:
        addmessage = ''
        if details:
            addmessage = \
                'Rep Details below. Delete or edit details to modify'
            return render_template('repdetails.html', salesrep=salesrep,
                               details=details, addmessage=addmessage,
                               salesrep_id=salesrep_id)
        else:
            return render_template('repdetails.html', salesrep=salesrep,
                                addmessage=addmessage, salesrep_id=salesrep_id)

# Add Rep Details

@app.route('/salesreps/<int:salesrep_id>/repdetails/add/',
           methods=['GET', 'POST'])
def addRepDetails(salesrep_id):
    if 'username' not in login_session:
        return redirect('/login')
    salesrep = session.query(SalesReps).filter_by(id=salesrep_id).one()
    salesrepdetails = \
        session.query(RepDetails).filter_by(salesrep_id=salesrep_id).all()
    if login_session['user_id'] != salesrep.user_id:
        return "<script>function myFunction() {alert('You are not authorized \
        to add Rep Details.');}</script><body onload='myFunction()''>"
    if request.method == 'POST' and len(salesrepdetails) < 1:
        newItem = RepDetails(
            name=salesrep.name,
            payout=request.form['payout'],
            sub_reps=request.form['sub_reps'],
            contractor=request.form['contractor'],
            salesrep_id=salesrep_id,
            user_id=salesrep.user_id,
            )

        session.add(newItem)
        session.commit()
        flash('Rep Details %s Successfully Added' % newItem.name)
        return redirect(url_for('showRep', salesrep_id=salesrep_id))
    elif request.method == 'POST':
        addmessage = 'Rep Details present. Must delete or edit'
        return redirect(url_for('showRep', salesrep_id=salesrep_id))
    else:
        return render_template('addRepDetails.html',
                               salesrep_id=salesrep_id,
                               salesrep_name=salesrep.name)


# Edit a rep details

@app.route('/salesreps/<int:salesrep_id>/repdetails/edit',
           methods=['GET', 'POST'])
def editRepDetails(salesrep_id):
    if 'username' not in login_session:
        return redirect('/login')
    salesrep = session.query(SalesReps).filter_by(id=salesrep_id).one()
    details = \
        session.query(RepDetails).filter_by(salesrep_id=salesrep_id).all()
    if login_session['user_id'] != salesrep.user_id:
        return "<script>function myFunction() {alert('You are not authorized \
        to edit Rep Details.');}</script><body onload='myFunction()''>"
    for i in details:
        if request.method == 'POST':
            if request.form['payout']:
                i.payout = request.form['payout']
            if request.form['sub_reps']:
                i.sub_reps = request.form['sub_reps']
            if request.form['contractor']:
                i.contractor = request.form['contractor']
            session.add(salesrep)
            session.commit()
            flash('Sales Rep Successfully Edited')
            return redirect(url_for('showRep', salesrep_id=salesrep_id))
        return render_template(
            'editRepDetails.html',
            salesrep_id=salesrep_id,
            salesrep_name=salesrep.name,
            details_payout=i.payout,
            details_sub_reps=i.sub_reps,
            details_contractor=i.contractor,
            )


# Delete a rep details

@app.route('/salesreps/<int:salesrep_id>/repdetails/delete',
           methods=['GET', 'POST'])
def deleteRepDetails(salesrep_id):
    if 'username' not in login_session:
        return redirect('/login')
    salesrep = session.query(SalesReps).filter_by(id=salesrep_id).one()
    details = \
        session.query(RepDetails).filter_by(salesrep_id=salesrep_id).first()
    if login_session['user_id'] != salesrep.user_id:
        return "<script>function myFunction() {alert('You are not authorized \
        to delete Rep Details.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(details)
        flash('Successfully Deleted Details for %s' % salesrep.name)
        session.commit()
        return redirect(url_for('showSalesReps', salesrep_id=salesrep_id))
    else:
        return render_template('deleteRepDetails.html',
                               salesrep_id=salesrep_id,
                               salesrep_name=salesrep.name)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True  # debug activated
    app.run(host='0.0.0.0', port=8000)
