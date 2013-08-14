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
import logging
import urllib2
import shutil
import sys
import os
from datetime import datetime

import json
import hashlib

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run
from apiclient import errors

# below is running at my home computer...so testing
scripthome =  os.path.join(os.getenv('HOME'), "pgDriveCheck")
#scripthome = os.path.join(os.getenv('HOME'), "Dropbox", "BackupSystem")
loghome = os.path.join(scripthome, "PGbackups.log")
logging.basicConfig(format='%(levelname)s:[%(asctime)-15s]: %(funcName)s: %(message)s',
                    filemode='w', filename=loghome, level=logging.INFO)
logger = logging.getLogger('PG-Backup')
archivedGDriveStateFilename  = os.path.join(scripthome, "fileMeta.json")

def main():
    logger.info("PeaceGeeks Google Drive auditor starting.")
    configFile      = "config.json"
    # XXX this should not be be using a hardcoded name
    configFile      = os.path.join(scripthome, configFile)
    defaultRunLimit = 3
    repeatSafety    = 0
    date            = datetime.now().strftime("%Y-%m-%d-%H-%M")
    
    try:
        configData = load_json_file(configFile)
        logger.debug("configuration data loaded")
        print("configuration data loaded")
    except Exception as e:
        print "There was an error loading the config file.\n  ERROR: %s" %e
        logger.error("Failed to load configuration data.  Exiting. %s", e)
        return
    try:
        # Check for args pass in when script was started or use default
        runLimit = sys.argv[1]
        try:
            # Check that a number was passed in as an agruement and nothing else
            sys.argv[1] += 1
        except TypeError:
            logger.warn("Bad value passed to script: %s is not an int", sys.argv[1])
            print ("Passed in something other than a number as an option with the script.  Use a number please.")
            print ("\"$ python %s 10\" \nwill run the %s script 10 times (it's actually more than that :)") %(sys.argv[0], sys.argv[0])
            raise
    except IndexError:
        print ("No run time loop limit given on script start.  Using default of %s") %defaultRunLimit
        logger.info("No run limit given.  Using default, %s", defaultRunLimit)
        runLimit = defaultRunLimit

    # Check for changes
    logger.debug("Performing first loop through check.")
    for repeatSafety in xrange(runLimit):
        if perform_check(configData, date) == 0:
            # This means it ran successfully so we don't need to do ANOTHER
            # backup
            break
        logger.WARN("Failed check.  Peforming loop %s", str(repeatSafety))
        repeatSafety += 1
    else:
        logger.info("Run limit hit.  Exiting.")
        print ("Exceeded max runlimit of %s.  Ending script.") %runLimit
        send_email("Drive Backups failed.  Please review log file.", configData, True)
    print ("We're all done here.  Make sure nothing went wrong in the logs.")
    logger.info("We're all done here.  Make sure nothing went wrong in the logs.")

def perform_check(configData, date):
    # Retrieve current data from google drive
    try:
        credentials = get_credentials(configData)
        print("Retrieved credentials config data successfully")
    except Exception as e:
        logger.error("Failed to retrieve Credentials.\nERROR: %s", e)
        return 1

    try:
        service = get_service(credentials)
        print("Retrieved service from Google successfully")
    except Exception as e:
        logger.error("Failed to retrieve Service.\n ERROR: %s", e)
        return 1

    try:
        currentGDriveState = retrieve_all_meta(service)
        logger.info("File meta data retrieved from Google successfully.")
    except Exception as e:
        message = """An error occurred while retrieving the data for your files from Google.
                    Checking State of variables.  True means variable exists.\n"""
        message += "Service State: %s\n" %(service != None)
        message += "Credentials State: %s\n" %(credentials != None)
        message += """If they are all true and it's still failing, you might
                    need to dig more.\n"""
        message += "ERROR: %s" %e
        logger.error(message)
        send_email(message, configData, True)
        return 1
    logger.info("Starting drive check.")
    # Check that the currentGDriveState was created
    
    try:
        # reload previous data from store JSON
        archivedGDriveState = load_json_file(archivedGDriveStateFilename)
        logger.info("Archived data retrieved.")
    except Exception as e:
        message = "Could not load archived meta data. Recover a backup. ERROR: %s" %e
        try:
            send_email(message, configData, 0)
            logger.error(message)
        except Exception as e:
            message = "Failed to send \"No recovery backup files\" email. %s %s"
            logger.error(message, "ERROR: ", e)
        finally:
            return 1

    # Creat list of folder ids for currentGDriveState and archivedGDriveState
    currentGDriveStateFolderIds  = get_all_pg_folder_ids(currentGDriveState)
    logger.debug("Current folder ID set retrieved.")
    archivedGDriveStateFolderIds = get_all_pg_folder_ids(archivedGDriveState)
    logger.debug("Archived folder ID set retrieved.")

    # Create sets out of the file IDs from archivedGDriveState and currentGDriveState that have
    # ids in the currentGDriveStateFolderIds list and archivedGDriveStateFolderIds list
    currentFileIDs = get_file_id_set(currentGDriveState, currentGDriveStateFolderIds)
    logger.debug("Current file ID set retrieved.")
    archivedFileIDs = get_file_id_set(archivedGDriveState, archivedGDriveStateFolderIds)
    logger.debug("Archived file ID set retrieved.")

    # Must check both directions just incase one is empty
    if len(currentFileIDs.difference(archivedFileIDs)) == 0 and len(archivedFileIDs.difference(currentFileIDs)) == 0:
        import os.path, time
        message = "PeaceGeeks Google Drive auditor ran successfully:\n"
        message += "There have been no changes to you Google Drive since %s" % time.ctime(os.path.getmtime("fileMetaData.json"))
        try:
            send_email(message, configData, 0)
            logger.info("\"No updates needed.\" email sent.")
        except Exception as e:
            message = "Failed to send \"No updates needed.\" email. %s %s"
            logger.error(message, "ERROR: ", e)

        print (message)

    else:
        removedFileIDs = get_difference(archivedFileIDs, currentFileIDs)
        logger.debug("Retrieved set of removed file IDs.")
        addedFileIDs   = get_difference(currentFileIDs, archivedFileIDs)
        logger.debug("Retrieved set of added file IDs.")
        #  Download added Files
        import getFiles
        succDnLds = 0
        for GDriveObject in currentGDriveState:
            if GDriveObject['mimeType'].find('folder') == -1:
                # XXX This will be if added AND if changed
                #if GDriveObject['id'] in addedFileIDs:
                dFile = getFiles.get_download_url(GDriveObject)
                if dFile != None:
                    filename = ""
                    content = ""
                    try:
                        content, filename = getFiles.download_file(service, dFile)
                    except Exception as e:
                        logger.error("%s: ERROR: %s", GDriveObject['title'], e)
                    # if this failed filename will be blank and an error was logged in logs
                    if filename != "":
                        try:
                            getFiles.write_file(content, filename, date)
                            succDnLds += 1
                            logger.debug("Downloaded and saved %s of %s. Retrieved: %s", succDnLds, len(currentFileIDs), filename)
                        except Exception as e:
                            logger.error("""Failed to write the file, %s: ERROR: %s""", filename, e)
        print ("%s of %s files have downloaded and saved") %(succDnLds, len(currentFileIDs))
        logger.info("%s of %s files have downloaded and saved", succDnLds, len(currentFileIDs))

        message = generate_added_removed_message(removedFileIDs, addedFileIDs, archivedGDriveState, currentGDriveState)
        try:
            message
            send_email(message, configData, False)
            logger.info(message)

        except Exception as e:
            message = "Failed to send Auditor report email.  Error: %s" %e
            logger.error(message)

    # don't create the json file yet or else you overwrite the check file.
    # Create backup folder and create dated file names for recovery
    try:
        #pass
        create_json_file_from_meta(currentGDriveState)
    except Exception as e:
        print (e)
        message = "Could not create archive file of current state. Error: %s" %e
        try:
            send_email(message, configData, 0)
            logger.error(message)
        except Exception as e:
            message = "Failed to send \"Could not create new archive\" email %s %s"
            logger.error(message, "ERROR: ", e)
        return 1

    return 0

#initially get the ID of Share PeaceGeeks folder
def get_Share_Peace_Id(folderData):
    geekFolderIds = []
    for item in folderData:
        if item['title'] == "Shared PeaceGeeks" or item['title'] == "PeaceGeeks Drive":
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
            # convert owner names away from unicode to a byte string
            owner = [name.encode("UTF-8") for name in file["ownerNames"]]
            message += "File name: %s\nFile Owner: %s\n\n" %(file["title"], owner)
    return message

def generate_added_removed_message(removedFileIDs, addedFileIDs, archivedGDriveState, currentGDriveState):
    message     = "=== Files Removed ===\n"
    message = get_title_owner(message, removedFileIDs, archivedGDriveState)
    message     += "\n=== Files Added ===\n"
    message = get_title_owner(message, addedFileIDs, currentGDriveState)
    return message

def send_email(message, configData, error):
    """Sends an email reporting a message of success or failure of the script.
       If error is true then the email is sent to it.  If error is false is sent
       to peacegeeks admin."""
    import smtplib
    #import email MIMEText to hold the unicode?  I guess
    import email.mime.text as text
    import email.mime.multipart as parts
    email = parts.MIMEMultipart()
    
    # Check if this is an email due to an error occurring.    
    if error:
        #This needs to be able to change TO location
        TO = configData['TOERROR']
    else:
        #This needs to be able to change TO location
        TO = configData['TOREPORT']
    # Convert the Unicode objects to UTF-8 encoding
    TO = [address.encode('utf-8') for address in TO]
    email['To'] = ','.join(e for e in TO)
    email['From'] = FROM = configData['FROM']
    email['Subject'] = "PeaceGeeks Server - Google Drive Report"
    
    body = text.MIMEText(message, _charset='utf-8')
    email.attach(body)

    # Attach log file to the email
    fname = os.path.basename(loghome)
    attachFile = open(loghome, 'r')
    attachFile = text.MIMEText(attachFile.read(), _charset='utf-8')
    attachFile.add_header('Content-Disposition', 'attachment', filename=fname)           
    email.attach(attachFile)
    
    
    SERVER = "localhost"
    server = smtplib.SMTP(SERVER)
    server.sendmail(FROM, TO, email.as_string())
    server.quit()

def load_json_file(jsonFile):
    with open(jsonFile, 'r') as fileData:
        jsonData = json.loads(fileData.read())
        fileData.close()
    return jsonData

def get_credentials(configData):
    #Could prompt for these credentials later.
    client_id = configData["CLIENTID"]
    client_secret = configData["CLIENTSECRET"]
    # The scope URL for read/write access to a user's calendar data
    scope         = 'https://www.googleapis.com/auth/drive.readonly'
    # Create a flow object. This object holds the client_id, client_secret, and
    # scope. It assists with OAuth 2.0 steps to get user authorization and
    # credentials.
    flow = OAuth2WebServerFlow(client_id, client_secret, scope)
    # Create a Storage object. This object holds the credentials that your
    # application needs to authorize access to the user's data. The name of the
    # credentials file is provided. If the file does not exist, it is
    # created. This object can only hold credentials for a single user, so
    # as-written, this script can only handle a single user.
    creds = os.path.join(scripthome,'credentials.dat')
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
        logger.debug("Credentials retrieved successfully.")
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
        logger.debug("Service retrieved successfully from Google.")
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

    XXX:
    Change this to files.list from the google drive api?  You can use the Google
    Drive suggest of drive_file.get('downloadUrl') since download url doesn't
    exist most of the time in the format I currently have.
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
    logger.debug("Archived drive state loaded successfully.")
    return result

def create_json_file_from_meta(stateJSON):
    try:
        filename = "archivedGDriveStateFilename"
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
