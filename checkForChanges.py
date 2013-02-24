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

import getFiles

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
    configFile      = "config.json"
    defaultRunLimit = 3
    repeatSafety    = 0
    try:
        configData = load_json_file(configFile)
    except :
        print "There was an error loading the config file."
        return
    try:
        # Check for args pass in when script was started or use default
        runLimit = sys.argv[1]
        try:
            # Check that a number was passed in as an agruement and nothing else
            sys.argv[1] += 1
        except TypeError:
            print ("Passed in something other than a number as an option with the script.  Use a number please.")
            print ("\"$ python %s 10\" \nwill run the %s script 10 times (it's actually more than that :)") %(sys.argv[0], sys.argv[0])
            return 1
    except IndexError:
        print ("No run time loop limit given on script start.  Using default of %s") %defaultRunLimit
        runLimit = defaultRunLimit

    # Check for changes
    while (perform_check(configData)):
        if repeatSafety <= runLimit:
            perform_check(configData)
            repeatSafety += 1
        else:
            print ("Exceeded max runlimit of %s.  Ending script.") %runLimit
            break
    print "We're all done here.  Make sure nothing went wrong."

def perform_check(configData):
    # Retrieve current data from google drive
    credentials  = get_credentials(configData)
    service      = get_service(credentials)
    currentState = retrieve_all_meta(service)
    archiveData  = "fileMetaData.json"

    try:
        # reload previous data from store JSON
        archivedState = load_json_file(archiveData)
    except:
        message = "Could not load archived meta data.  Recover a backup."
        #send_email(message, configData)
        print (message)
        return 0

    # Creat list of folder ids for currentState and archivedState


    currentStateFolderIds  = get_All_PeaceGeek_Folder_Ids(currentState)
    archivedStateFolderIds = get_All_PeaceGeek_Folder_Ids(archivedState)

    # Create sets out of the ids from archivedState and currentState that have
    # ids in the currentStateFolderIds list and archivedStateFolderIds list
    currentIds = set()
    if None != currentState:
        currentIds = get_id_set(currentState, currentStateFolderIds)
    else:
        print "An error occurred while retrieving the data for your files."
        print "Checking State of variables.  True means variable exists."
        print "Service State: %s" %(service != None)
        print "Credentials State: %s" %(credentials != None)
        print "Current Meta Data: %s" %( currentIds != None)
        print "If they are all true and it's still failing, you might need to dig more."
        return 1
    archivedIds = get_id_set(archivedState, archivedStateFolderIds)

    if currentIds == archivedIds:
        message = "There have been no changes to you Google Drive since (previous date checked)"
        #print send_email(message)
        print (message)

    else:
        ##########################################################################
        #  Create function that downloads files if they are added.
        #  Criteria is changed or added.
        #  Add functionality to look for changes in files by checking changed date
        ##########################################################################


        removedIds = get_difference(archivedIds, currentIds)
        addedIds   = get_difference(currentIds, archivedIds)
        message    = generate_added_removed_message(removedIds, addedIds, archivedState, currentState)
        #print send_email(message)
        print (message)

    #don't create the json file yet or else you overwrite the check file.
    # Create backup folder and create dated file names for recovery
    try:
        pass
        #create_json_file_from_meta(service)
    except:
        message = """Could not create new State file.
                     Some how lost your internet connect between starting this script and now."""
        #print send_email(message)
        print (message)
        return 1

    return 0

#initially get the ID of Share PeaceGeeks folder
def get_Share_Peace_Id(folderData):
    geekFolderIds = []
    for item in folderData:
        if item['title'] == "Shared PeaceGeeks":
            geekFolderIds.append(item['id'])
            folderData.remove(item)
            break
    return set(geekFolderIds)


# Loop through jsonState looking for folders which have a parent id under the Shared PeaceGeeks
# hierarchy.  When the list geekFolderIds stops growing then stop the loop.
def get_All_PeaceGeek_Folder_Ids(jsonState):
    ###
    ###  THIS IS ALL GOING TO GET REPLACED BY Union-Find AS SUGGESTED BY Mark.
    ###
    jsonStateCopy           = jsonState[:]
    geekFolderIds           = get_Share_Peace_Id(jsonStateCopy)
    getSharePeaceIDListSize = len(geekFolderIds)
    while True:
        for item in jsonStateCopy:
            if item['mimeType'].find('folder') != -1:
                if item['parents']:
                    parent = item['parents']
                    if parent[0]['id'] in geekFolderIds:
                        # There can be duplicate folders easily in the Google Drive interface
                        # so remove any that have already been added.
                        if item['id'] in geekFolderIds:
                            jsonStateCopy.remove(item)
                        else:
                            geekFolderIds.add(item['id'])
                            jsonStateCopy.remove(item)
                    else:
                        pass
                else:
                    jsonStateCopy.remove(item)
            else:
                jsonStateCopy.remove(item)
        if len(geekFolderIds) == getSharePeaceIDListSize:
            break
        else:
            getSharePeaceIDListSize = len(geekFolderIds)
    return list(geekFolderIds)

# get ids that are in the Shared PeaceGeeks Hierarchy.
def get_id_set(jsonState, listOfIds):
    idSet = set()
    if None != jsonState:
        for file in jsonState:
            if file['mimeType'].find('folder') != -1 and file["parents"] and file["parents"][0]["id"] in listOfIds:
            #for item in file["parents"]:
            #    if item[0]["id"] in listOfIds:
                idSet.add(file["id"])
                    #currentIds[hashlib.sha224(file["id"]).hexdigest()] = file["id"]
    return idSet

def get_difference(setOne, setTwo):
    diff = setOne.difference(setTwo)
    return diff

def get_title_owner(message, ids, state):
    for file in state:
        if file["id"] in ids:
            message += "File name: %s\nFile Owner: %s\n" %(file["title"],file["ownerNames"])
    return message

def generate_added_removed_message(removedIds, addedIds, archivedState, currentState):
    message     = "=== Files Removed ===\n"
    get_title_owner(message, removedIds, archivedState)
    message     += "\n=== Files Added ==="
    get_title_owner(message, addedIds, currentState)
    return message

def send_email(message, configData):
    SERVER = "localhost"
    FROM = configData["FROM"]
    #This needs to be able to change TO location
    TO = configData["TOREPORT"]
    # Convert the Unicode objects to UTF-8 encoding
    TO = [address.encode('utf-8') for address in TO]
    SUBJECT = "PeaceGeeks Server - Google Drive Report"
    TEXT = message
    email = "From: %s\nTo: %s\nSubject: %s\n%s" %(FROM, ", ".join(TO),SUBJECT,TEXT)
    server = smtplib.SMTP(SERVER)
    server.sendmail(FROM,TO,email)
    return email

def load_json_file(jsonFile):
    with open(jsonFile, 'r') as fileData:
        jsonData = json.loads(fileData.read())
        fileData.close()
    return jsonData

def get_credentials(configData):
    #Could prompt for these credentials later.
    client_id     = configData["CLIENTID"]
    client_secret = configData["CLIENTSECRET"]
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
    else:
        print "Could not create service."
    return result

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
