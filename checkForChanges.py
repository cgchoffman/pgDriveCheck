#!/usr/bin/python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import httplib2
import urllib2
import urllib
import shutil
import sys
import os

import json
import hashlib
import smtplib

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run
from apiclient import errors


def main():
    defaultRunLimit = 10
    repeatSafety = 0
    try:
        runLimit = sys.argv[1]
        try:
            sys.argv[1] += 1
        except TypeError:
            print ("Passed in something other than a number as an option with the script.  Use a number please.")
            print ("\"$ python %s 10\" \nwill run the %s script 10 times (it's actually more than that :)") %(sys.argv[0], sys.argv[0])
            return 1
    except IndexError:
        print ("No run time loop limit given on script start.  Using default of %s") %defaultRunLimit
        runLimit = defaultRunLimit
    while (perform_check()):
        if repeatSafety <= runLimit:
            perform_check()
            repeatSafety += 1
        else:
            print ("Exceeded max runlimit of %s.  Ending script.") %runLimit
            break

def perform_check():
    # Retrieve current data from google drive
    credentials   = get_credentials()
    service       = get_service(credentials)
    currentState  = retrieve_all_meta(service)
    # reload previous data from store JSON
    archivedState = ""
    loadJsonMetaData = "fileMetaData.json"
    with open(loadJsonMetaData, 'r') as fileData:
        archivedState = json.loads(fileData.read())
        fileData.close()    
    #archivedState = json.loads(open( "fileMetaData.json", "r" ).read())
    
    # Create sets out of the ids from archivedState and currentState to compare
    currentIds = set()
    if None != currentState: 
        currentIds    = get_id_set(currentState)
    else:
        print "An error occurred while retrieving the data for your files."
        print "Checking State of variables.  True means variable exists."
        print "Service State: %s" %(service != None)
        print "Credentials State: %s" %(credentials != None)
        print "Current Meta Data: %s" %( currentIds != None)
        print "If they are all true and it's still failing, you might need to dig more."
        return 1
    archivedIds   = get_id_set(archivedState)
    
    if currentIds == archivedIds:
        message = "There have been no changes to you Google Drive since (previous date checked)"
        #print send_email(message)
        print (message)
        
    else:
        message = generate_added_removed_message(archivedState, archivedIds, currentState, currentIds)
        #print send_email(message)
        print (message)
    
    #don't create the json file yet or else you overwrite the check file.
    try:
        create_json_file_from_meta(service)
    except:
        message = """Could not create new State file.
                     Some how lost your internet connect between starting this script and now."""
        #print send_email(message)
        print (message)
        return 1
    
    return 0

def get_id_set(jsonState):
    idSet = set()
    if None != jsonState: 
        for file in jsonState:
            idSet.add(file["id"])
            #currentIds[hashlib.sha224(file["id"]).hexdigest()] = file["id"]
    return idSet

def generate_added_removed_message(archivedState, archivedIds, currentState, currentIds):
    removedIds = archivedIds.difference(currentIds)
    message     = "=== Files Removed ==="
    for file in archivedState:
        if file["id"] in removedIds:
            message += "\nFile name: %s\nFile Owner: %s" %(file["title"],file["ownerNames"])
    addedIds   = currentIds.difference(archivedIds)
    message     += "\n\n=== Files Added ==="
    for file in currentState:
        if file["id"] in addedIds:
            message += "\nFile name: %s\nFile Owner: %s" %(file["title"],file["ownerNames"])
    return message

def send_email(message):
    configDataJson = load_config_data()
    SERVER = "localhost"
    FROM = configDataJson["FROM"]
    
    TO = configDataJson["TOREPORT"]
    # Convert the Unicode objects to UTF-8 encoding
    TO = [address.encode('utf-8') for address in TO]
    SUBJECT = "PeaceGeeks Server - Google Drive Report"
    TEXT = message
    email = "From: %s\nTo: %s\nSubject: %s\n%s" %(FROM, ", ".join(TO),SUBJECT,TEXT)
    server = smtplib.SMTP(SERVER)
    server.sendmail(FROM,TO,email)
    return email

def load_config_data():
    # example config file contents.  Values can be what you like as long as they match that TYPE of data (email address, client_id)
    #  {"TO": ["carey@peacegeeks.org"], "FROM": "it@peacegeeks.org", "CLIENTID": "longstringoflettersandnyumbers666.apps.googleusercontent.com", "CLIENTSECRET":"string_of_lettersandnumbers"}

    configDataJson = ""
    loadConfigFile = "config.json"
    # Add Try that will start a create_config_file function
    # if one doesn't exist.
    with open(loadConfigFile, 'r') as configData:
        configDataJson = json.loads(configData.read())
        configData.close()
    return configDataJson

def get_credentials():
    configDataJson = load_config_data()
    #Could prompt for these credentials later.
    client_id     = configDataJson["CLIENTID"]
    client_secret = configDataJson["CLIENTSECRET"]
    # The scope URL for read/write access to a user's calendar data
    scope         = 'https://www.googleapis.com/auth/drive.readonly'
    # Create a flow object. This object holds the client_id, client_secret, and
    # scope. It assists with OAuth 2.0 steps to get user authorization and
    # credentials.
    flow          = OAuth2WebServerFlow(client_id, client_secret, scope)
    # Create a Storage object. This object holds the credentials that your
    # application needs to authorize access to the user's data. The name of the
    # credentials file is provided. If the file does not exist, it is
    # created. This object can only hold credentials for a single user, so
    # as-written, this script can only handle a single user.
    storage = Storage('credentials.dat')
  
    # The get() function returns the credentials for the Storage object. If no
    # credentials were found, None is returned.
    credentials = storage.get()
  
    # If no credentials are found or the credentials are invalid due to
    # expiration, new credentials need to be obtained from the authorization
    # server. The oauth2client.tools.run() function attempts to open an
    # authorization server page in your default web browser. The server
    # asks the user to grant your application access to the user's data.
    # If the user grants access, the run() function returns new credentials.
    # The new credentials are also stored in the supplied Storage object,
    # which updates the credentials.dat file.
    if credentials is None or credentials.invalid:
        credentials = run(flow, storage)
    return credentials

def get_service(credentials):
    # Create an httplib2.Http object to handle our HTTP requests, and authorize it
    # using the credentials.authorize() function.
    http = httplib2.Http()
    http = credentials.authorize(http)
    
    # The apiclient.discovery.build() function returns an instance of an API service
    # object can be used to make API calls. The object is constructed with
    # methods specific to the calendar API. The arguments provided are:
    #   name of the API ('calendar')
    #   version of the API you are using ('v2')
    #   authorized httplib2.Http() object that can be used for API calls
    try:
        service = build('drive', 'v2', http=http)
    except httplib2.ServerNotFoundError, httpError:
        print "An error occurred attempting to connect to your Google Drive. \n",\
        "Check that you are conntected to the internet.", httpError
        return
    return service
        
def retrieve_all_meta(service):
    """Retrieve a list of File resources.
  
    Args:
      service: Drive API service instance.
    Returns:
      List of File resources.
    """
    if service:
        result = []
        page_token = None
        while True:
            try:
                param = {}
                if page_token:
                    param['pageToken'] = page_token
                files = service.files().list(**param).execute()
          
                result.extend(files['items'])
                page_token = files.get('nextPageToken')
                if not page_token:
                    break
            except errors.HttpError, error:
                print 'An error occurred: %s' %error
                break
        # Remove any folders from metadata
        for item in result:
            if item['mimeType'].find("folder") > -1: 
                result.remove(item)
        return result
    print "Could not create service."
    
def create_json_file_from_meta(service):
    try:
        all_files_meta = retrieve_all_meta(service)# returns result[]
        filename = "fileMetaData.json"
        with open(filename, 'w') as dst:
            json.dump(all_files_meta, dst)
            dst.close()
    
    except AccessTokenRefreshError:
        # The AccessTokenRefreshError exception is raised if the credentials
        # have been revoked by the user or they have expired.
        print ('The credentials have been revoked or expired, please re-run'
               'the application to re-authorize')

def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
      try:
        os.makedirs(d)
      except Exception as e:
        return e    

if __name__ == '__main__':
    main() 