#!/usr/bin/python
#
# This file is used to create a manual backup of the entire drive.
# if for whatever reason the process gets interupted or corrupted
# Steps:
# - retrieve information about the drives contents
# - make a list of the file ids to download
# - download the files
# - create a new savedState file for later automatic runs of the backup
#   to use as a references for making subsequent backups and not downloading
#   what it doesn't have to
#
#   This should eventually get added to checkforChanges.py with an option to
#   do a manual backup.

import getFiles

import httplib2
import logging
import urllib2
import shutil
import sys
import os
from datetime import datetime

import json
import hashlib
import smtplib

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run
from apiclient import errors

scripthome = os.getcwd()
home = os.getenv('USERPROFILE') or os.getenv('HOME')
backuppath = os.path.join(home, "driveBackup")
corepath = os.path.join(backuppath,"core")
if os.path.exists(corepath):
    message = "back folder, %s, already exists.  Delete or move it first." %corepath
    print(message)
    sys.exit()
logginghome = os.path.join(scripthome, "PGbackups.log")
logging.basicConfig(format='[%(asctime)-15s]: %(funcName)s:  %(message)s',
                    filemode='w', filename=logginghome, level=logging.DEBUG)

def main():
    logging.info("PeaceGeeks Google Drive auditor starting.")
    configFile      = "config.json"
    # XXX this should not be be using a hardcoded name
    configFile      = os.path.join(scripthome, configFile)
    defaultRunLimit = 3
    repeatSafety    = 0
    date            = datetime.now().strftime("%Y-%m-%d-%H-%M")
    try:
        configData = load_json_file(configFile)
        logging.debug("configuration data loaded")
        print("configuration data loaded")
    except Exception as e:
        print "There was an error loading the config file.\n  ERROR: %s" %e
        logging.error("Failed to load configuration data.  Exiting. %s", e)
        return
    try:
        # Check for args pass in when script was started or use default
        runLimit = sys.argv[1]
        try:
            # Check that a number was passed in as an agruement and nothing else
            sys.argv[1] += 1
        except TypeError:
            logging.warn("Bad value passed to script: %s is not an int", sys.argv[1])
            print ("Passed in something other than a number as an option with the script.  Use a number please.")
            print ("\"$ python %s 10\" \nwill run the %s script 10 times (it's actually more than that :)") %(sys.argv[0], sys.argv[0])
            raise
    except IndexError:
        print ("No run time loop limit given on script start.  Using default of %s") %defaultRunLimit
        logging.info("No run limit given.  Using default, %s", defaultRunLimit)
        runLimit = defaultRunLimit

    # Check for changes
    logging.debug("Performing first loop through check.")
    while (perform_check(configData, date)):
        if repeatSafety <= runLimit:
            logging.WARN("Failed check.  Peforming loop %s", repeatSafety)
            perform_check(configData)
            repeatSafety += 1
        else:
            logging.info("Run limit hit.  Exiting.")
            print ("Exceeded max runlimit of %s.  Ending script.") %runLimit
            break
        print ("We're all done here.  Make sure nothing went wrong in the logs.")
        logging.info("We're all done here.  Make sure nothing went wrong in the logs.")

def perform_check(configData, date):
    # Retrieve current data from google drive
    try:
        credentials = get_credentials(configData)
    except Exception as e:
        logging.error("Failed to retrieve Credentials.\nERROR: %s", e)
        return 1

    try:
        service = get_service(credentials)
    except Exception as e:
        logging.error("Failed to retrieve Service.\n ERROR: %s", e)
        return 1

    try:
        currentGDriveState = retrieve_all_meta(service)
        logging.info("File meta data retrieved from Google successfully.")
    except Exception as e:
        message = """An error occurred while retrieving the data for your files.
                    Checking State of variables.  True means variable exists.\n"""
        message += "Service State: %s\n" %(service != None)
        message += "Credentials State: %s\n" %(credentials != None)
        message += """If they are all true and it's still failing, you might
                    need to dig more.\n"""
        message += "ERROR: %s" %e
        logging.error(message)
        return 1
    logging.debug("Starting drive check.")
    # Check that the currentGDriveState was created

    # Creat list of folder ids for currentGDriveState and archivedGDriveState
    currentGDriveStateFolderIds  = get_all_pg_folder_ids(currentGDriveState)
    logging.debug("Current folder ID set retrieved.")
    
    # Create sets out of the file IDs from archivedGDriveState and currentGDriveState that have
    # ids in the currentGDriveStateFolderIds list and archivedGDriveStateFolderIds list
    currentFileIDs = get_file_id_set(currentGDriveState, currentGDriveStateFolderIds)
    logging.debug("Current file ID set retrieved.")


    # Download added Files
    error = None
    try:
        retrieve_files(service, currentFileIDs, currentGDriveState, corepath)    
    except Exception as e:
        logging.error("failed to download files.")
        logging.error(e)
    

    try:
        create_json_file_from_meta(currentGDriveState)
    except Exception as e:
        print (e)
        message = "Could not create archive file of current state. Error: %s" %e
        try:
            send_email(message, configData, 0)
            logging.error(message)
        except Exception as e:
            message = "Failed to send \"Could not create new archive\" email %s %s"
            logging.error(message, "ERROR: ", e)
        logging.error(message)
        return 1
    try:
        send_email("Manual Drive backup completed successfully", configData, 0)
        logging.debug("Final email sent.")
    except Exception as e:
        print ("Failing gracefully because you haven't fixed the email issue...")
        print (e)

    return 0

def retrieve_files(service, currentFileIDs, currentGDriveState, downloadpath):
    import getFiles
    succDnLds = 0
    for GDriveObject in currentGDriveState:
        if GDriveObject['mimeType'].find('folder') == -1:
            if GDriveObject['id'] in currentFileIDs:
                dFile = getFiles.get_download_url(GDriveObject)
                if dFile != None:
                    try:
                        content, filename = getFiles.download_file(service, dFile)
                        getFiles.write_file(content, filename, downloadpath)
                        succDnLds += 1
                        logging.debug("Downloading %s of %s", succDnLds, len(currentFileIDs))
                    except Exception as e:
                        logging.error("""Failed to download or write the file.
                                      \nERROR: %s""", e)
    print ("%s of %s files have downloaded and saved") %(succDnLds, len(currentFileIDs))
    logging.info("%s of %s files have downloaded and saved", succDnLds, len(currentFileIDs))


#initially get the ID of Share PeaceGeeks folder
def get_Share_Peace_Id(folderData):
    geekFolderIds = []
    for item in folderData:
        if item['title'] == "Shared PeaceGeeks" or item['title'] == "PeaceGeeks Drive" or item['title'] == "PeaceGeeks Drive3":
            geekFolderIds.append(item.get('id'))
            folderData.remove(item)
            break
    return set(geekFolderIds)

def create_list_of_files(idSet, jsonState):
    jsonStateCopy = jsonState[:]
    for item in jsonStateCopy:
        if item['id'] not in idSet:
            jsonStateCopy.remove(item)
    return jsonStateCopy


# Loop through jsonState looking for folders which have a parent id under the Shared PeaceGeeks
# hierarchy.  When the list geekFolderIds stops growing then stop the loop.
def get_all_pg_folder_ids(jsonState):
    ###
    ###  THIS IS ALL GOING TO GET REPLACED BY Union-Find AS SUGGESTED BY Mark.
    ###
    jsonStateCopy           = jsonState[:]
    geekFolderIds           = get_Share_Peace_Id(jsonStateCopy)
    getSharePeaceIDListSize = len(geekFolderIds)
    while True:
        for item in jsonStateCopy:
            if item['mimeType'].find('folder') > -1:
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
    return list(set(geekFolderIds))

# get ids of FILES that are in the Shared PeaceGeeks Hierarchy.
def get_file_id_set(jsonState, listOfIds):
    idSet = set()
    if None != jsonState:
        for file in jsonState:
            if file['mimeType'].find('folder') == -1 and file["parents"] and file["parents"][0]["id"] in listOfIds:
            #for item in file["parents"]:
            #    if item[0]["id"] in listOfIds:
                idSet.add(file["id"])
                    #currentFileIDs[hashlib.sha224(file["id"]).hexdigest()] = file["id"]
    return idSet

def get_difference(setOne, setTwo):
    diff = setOne.difference(setTwo)
    return diff

def get_title_owner(message, ids, state):
    for file in state:
        if file["id"] in ids:
            message += "File name: %s\nFile Owner: %s\n" %(file["title"],file["ownerNames"])
    return message

def generate_added_removed_message(removedFileIDs, addedFileIDs, archivedGDriveState, currentGDriveState):
    message     = "=== Files Removed ===\n"
    message = get_title_owner(message, removedFileIDs, archivedGDriveState)
    message     += "\n=== Files Added ==="
    message = get_title_owner(message, addedFileIDs, currentGDriveState)
    return message

def send_email(message, configData, error):
    """Sends an email reporting a message of success or failure of the script.
       If error is true then the email is sent to it.  If error is false is sent
       to peacegeeks admin."""
    if error:
        #This needs to be able to change TO location
        TO = configData['TOERROR']
    else:
        #This needs to be able to change TO location
        TO = configData["TOREPORT"]
    # Convert the Unicode objects to UTF-8 encoding
    TO = [address.encode('utf-8') for address in TO]
    SERVER = "localhost"
    FROM = configData["FROM"]
    SUBJECT = "PeaceGeeks Server - Google Drive Report"
    email = "From: %s\nTo: %s\nSubject: %s\n%s" %(FROM, ", ".join(TO),SUBJECT,message)
    server = smtplib.SMTP(SERVER)
    server.sendmail(FROM,TO,email)
    return email

def load_json_file(jsonFile):
    import simplejson
    with open(jsonFile, 'r') as f:
        jsonData = simplejson.loads(f.read())
        f.close()
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
    creds= os.path.join(scripthome,'credentials.dat')
    storage = Storage(creds)

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
        logging.debug("Credentials retrieved successfully.")
    return credentials

def get_service(credentials):
    # Create an httplib2.Http object to handle our HTTP requests, and authorize it
    # using the credentials.authorize() function.
    http = httplib2.Http()
    http.disable_ssl_certificate_validation = True
    http = credentials.authorize(http)

    # The apiclient.discovery.build() function returns an instance of an API service
    # object can be used to make API calls. The object is constructed with
    # methods specific to the calendar API. The arguments provided are:
    #   name of the API ('calendar')
    #   version of the API you are using ('v2')
    #   authorized httplib2.Http() object that can be used for API calls
    try:
        service = build('drive', 'v2', http=http)
        logging.debug("Service retrieved successfully from Google.")
    except httplib2.ServerNotFoundError, httpError:
        # XXX this raise doesnt work at all
        raise ("An error occurred attempting to connect to your Google Drive. \n",
        "Check that you are conntected to the internet.", httpError)
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
                raise 'An error occurred: %s' %error
                break
    else:
        raise "Service is None"
    logging.debug("Archived drive state loaded successfully.")
    return result

def create_json_file_from_meta(stateJSON):
    try:
        filename = "fileMetaData.json"
        with open(filename, 'w') as dst:
            json.dump(stateJSON, dst)
            dst.close()
        print ("Archived PG Drive created.  Thanks!")

    except IOError as (errno, strerror):
        raise
    except:
        raise


if __name__ == '__main__':
    main()
