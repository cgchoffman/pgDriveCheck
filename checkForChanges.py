#!/usr/bin/python
# This file backsup a given google drive account based on a users credentials.
# It saves a state file so that later backups won't download what doesn't
# need downloading based on:
#  - changed files
#  - added files
# It also emails a user with a report of what's been been:
#  - changed
#  - added
#  - deleted
# Deleted files are never removed from the backup
#
# To start from scratch and do a full backup rename the savedState.json  file
# and the script will do a full backup and create a new savedState.json file


import getFiles
import Drive_Checker

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


#checker = Drive_Checker.DriverChecker()
scripthome = os.getcwd()
loghome = os.path.join(scripthome, "PGbackups.log") # Logs home
home = os.getenv('USERPROFILE') or os.getenv('HOME')
backuppath = os.path.join(home, "driveBackup")
corepath = os.path.join(backuppath,"core")
date = datetime.now().strftime("%Y-%m-%d-%H-%M")
datebackuppath = os.path.join(backuppath, date) # this path and core path should be cleansed
                                                # if they ever take input from users as they
                                                # are used for system calls later
logging.basicConfig(format='%(levelname)s:[%(asctime)-15s]: %(funcName)s: %(message)s\n\t%(exc_info)s',
                    filemode='w', filename=loghome, level=logging.INFO)
logger = logging.getLogger('PG-Backup')
logger.setLevel("DEBUG")
archivedGDriveStateFilename = os.path.join(scripthome, "savedState.json")
if not os.path.exists(archivedGDriveStateFilename):
    archivedGDriveStateFilename = ""

configFile      = "config.json"
# XXX this should not be be using a hardcoded name
# and should be a classmember
configFile      = os.path.join(scripthome, configFile)

# This should be a member...you should be a member :P
configData = {}


def main():
    logger.info("PeaceGeeks Google Drive auditor starting.")
    # This should be a member function
    global configData
    try:
        configData = load_json_file(configFile)
        logger.debug("configuration data loaded")
        print("configuration data loaded")
    except Exception as e:
        configData = None
        message = "Failed to load configuration data.  Exiting. %s" %e
        logger.error(message)
        send_email(message, configData, True)
        return
    
    defaultRunLimit = 1
    repeatSafety    = 0
    
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
        try:
            perform_check(configData, datebackuppath)
            break
        except Exception as e:
            message = "perform_check failed: %s" %e
            logger.error(message)
            try:
                send_email(message, configData, True)
            except Exception as e:
                message = "Failed to send \"No recovery backup files\" email. %s %s"
                logger.error(message, "ERROR: ", e)
            repeatSafety += 1
            
    print ("We're all done here.  Make sure nothing went wrong in the logs.")
    logger.info("We're all done here.  Make sure nothing went wrong in the logs.")

def perform_check(configData, datebackuppath):
    # Retrieve current data from google drive
    try:
        credentials = get_credentials(configData)
        print("Retrieved credentials config data successfully")
    except Exception as e:
        # the better way to do this is to 
        message = "Failed to retrieve Credentials.\nERROR: %s" %e
        raise Exception(message)

    try:
        service = get_service(credentials)
        print("Retrieved service from Google successfully")
    except Exception as e:
        message = "Failed to retrieve Service.\n ERROR: %s" %e
        raise Exception(message)

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
        raise Exception(message)
    
    logger.info("Starting drive check.")
    # Check that the currentGDriveState was created

    # Creat list of folder ids for currentGDriveState and archivedGDriveState
    currentGDriveStateFolderIds  = get_all_pg_folder_ids(currentGDriveState)
    logger.debug("Current folder ID set retrieved.")
    currentFileIDs = get_file_id_set(currentGDriveState, currentGDriveStateFolderIds)
    logger.debug("Current file ID set retrieved.")
        
    try:
        # if failed to load archived file, or I removed it
        if archivedGDriveStateFilename == "":
            logger.info("No archived file.  Performing full backup")
            
            try:
                # Download all Files
                retrieve_all_files(service, currentFileIDs, currentGDriveState, datebackuppath)
                # Create backup folder and create dated file names for recovery
                try:
                    create_json_file_from_meta(currentGDriveState)
                except Exception as e:
                    message = "Could not create archive file of current state. Error: %s" %e
                    raise Exception(message)
                return 0
            except Exception as e:
                message = "Tried to perform full backup recovery but failed.  Fix it: %s" %e
                raise Exception(message)

        else:
            archivedGDriveState = load_json_file(archivedGDriveStateFilename)
            logger.info("Archived data retrieved.")  
        
    except Exception as e:
        message = "Could not load archived meta data. Recover a backup. ERROR: %s" %e
        raise Exception(message)
    
    archivedGDriveStateFolderIds = get_all_pg_folder_ids(archivedGDriveState)
    logger.debug("Archived folder ID set retrieved.")
    archivedFileIDs = get_file_id_set(archivedGDriveState, archivedGDriveStateFolderIds)
    logger.debug("Archived file ID set retrieved.")

    download_diff(archivedFileIDs, currentFileIDs, archivedGDriveState, currentGDriveState, archivedGDriveStateFolderIds, currentGDriveStateFolderIds)
    
    # Create backup folder and create dated file names for recovery
    try:
        create_json_file_from_meta(currentGDriveState)
    except Exception as e:
        message = "Could not create archive file of current state. Error: %s" %e
        raise Exception(message)
    return 0

# rsync the dated folder with the core folder
# This was the easiest way to write a file to folder that would already have
# said folder in it.
def rsync_rm():
    from os import system as s
    try:
        rsync = "rsync -av %s/ %s" % (datebackuppath, corepath)
        s(rsync)
    except Exception as e:
        message = "Failed to rsync folders %s with %s.  Error: %s" %(corepath, datebackuppath, e)
        logger.error(message)
        try:
            send_email(message, configData, True)
        except Exception as e:
            message = "Failed to send Auditor report email.  Error: %s" %e
            logger.error(message)
    try:
        remove = "rm -r %s" % datebackuppath
        s(remove)
    except Exception as e:
        message = "Failed to remove dated folder.  Error: %s" %e
        logger.error(message)

def retrieve_all_files(service, currentFileIDs, currentGDriveState, downloadpath):
    
    logging.info("****************Performing Full backup of drive.****************")
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
    rsync_rm()
    message = "%s of %s files have downloaded and saved"  %(succDnLds, len(currentFileIDs))
    logging.info(message)
    send_email(message, configData, False)

# only download the files that have changed or been added to the drive
# True for download done, False for no changes, nothing downloaded
# This is BS.  I gotta get on making this into a class!
def download_diff(archivedFileIDs, currentFileIDs, archivedGDriveState, currentGDriveState, archivedGDriveStateFolderIds, currentGDriveStateFolderIds):
    
    logging.info("Performing Diff backup")
    # Must check both directions just incase one is empty
    if len(currentFileIDs.difference(archivedFileIDs)) == 0 and len(archivedFileIDs.difference(currentFileIDs)) == 0:
        import os.path, time
        message = "PeaceGeeks Google Drive auditor ran successfully:\n"
        message += "There have been no changes to you Google Drive since %s" % time.ctime(os.path.getmtime(archivedGDriveStateFilename))
        try:
            send_email(message, configData,  False)
            logger.info("\"No updates needed.\" email sent.")
        except Exception as e:
            message = "Failed to send \"No updates needed.\" email. %s %s"
            logger.error(message, "ERROR: ", e)

        return False

    else:
        removedFileIDs = get_difference(archivedFileIDs, currentFileIDs)
        logger.debug("Retrieved set of removed file IDs.")
        addedFileIDs = get_difference(currentFileIDs, archivedFileIDs)
        logger.debug("Retrieved set of added file IDs.")
        
        reformatCurrent = reformatDrive(currentGDriveState, currentGDriveStateFolderIds)
        reformatArchive = reformatDrive(archivedGDriveState, archivedGDriveStateFolderIds)
        
        modfiedFileIDs = getModifiedFiles(reformatCurrent, reformatArchive)
        
        #  Download added Files
        import getFiles
        succDnLds = 0
        for GDriveObject in currentGDriveState:
            # XXX This will be if added or if changed
            if GDriveObject['id'] in modfiedFileIDs or GDriveObject['id'] in addedFileIDs:
                if GDriveObject['mimeType'].find('folder') == -1:
                    dFile = getFiles.get_download_url(GDriveObject)
                    if dFile == None:
                        dFile = getFiles.get_export_link(GDriveObject)
                    filename = ""
                    content = ""
                    try:
                        content, filename = getFiles.download_file(service, dFile)
                    except Exception as e:
                        logger.error("%s: ERROR: %s", GDriveObject['title'], e)
                    # if this failed filename will be blank and an error was logged in logs
                    if filename != "":
                        try:
                            getFiles.write_file(content, filename, datebackuppath)
                            succDnLds += 1
                            logger.debug("Downloaded and saved %s of %s. Retrieved: %s", succDnLds, len(currentFileIDs), filename)
                        except Exception as e:
                            logger.error(e)
        rsync_rm()
        downloadsMessage = ("%s of %s files have downloaded and saved") %(succDnLds, (len(addedFileIDs) + len(modfiedFileIDs)))
        message = generate_added_removed_modifed_message(removedFileIDs, addedFileIDs, archivedGDriveState, currentGDriveState, modfiedFileIDs)
        message += downloadsMessage
        try:
            send_email(message, configData, False)
            logger.info(message)
            logger.info(downloadsMessage)
        except Exception as e:
            message = "Failed to send Auditor report email.  Error: %s" %e
            logger.error(message)
        return True
        
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
    ###  THIS IS ALL GOING TO GET REPLACED BY Union-Find AS SUGGESTED BY MarkY.
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
            filename = file["title"]
            owner = [name.encode("UTF-8") for name in file["ownerNames"]]
            createdDate = file['createdDate']
            message += "File name: %s\nFile Owner: %s\nCreated: %s\n\n" %(filename, owner, createdDate)
    return message

def generate_added_removed_modifed_message(removedFileIDs, addedFileIDs, archivedGDriveState, currentGDriveState, modifiedIDs):
    message = "=== Files Removed ===\n"
    message = get_title_owner(message, removedFileIDs, archivedGDriveState)
    message += "\n=== Files Added ===\n"
    message = get_title_owner(message, addedFileIDs, currentGDriveState)
    message += "\n===Modfied Files===\n"
    message = get_title_owner(message, modifiedIDs, currentGDriveState)
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
    # if configData is None that means the config couldn't be loaded
    #  hardcode my email to me.
    subject = ""
    FROM = "security@peacegeeks.org"
    if configData == None:
        TO = ["cgchoffman@gmail.com"]
    elif error:
        #This needs to be able to change TO location
        TO = configData['TOERROR']
        subject = "ERROR OCCURRED - PANIC! - "
    else:
        #This needs to be able to change TO location
        TO = configData['TOREPORT']
        subject = "SUCCESS - "
    # Convert the Unicode objects to UTF-8 encoding
    TO = [address.encode('utf-8') for address in TO]
    email['To'] = ','.join(e for e in TO)
    subject += "PeaceGeeks Server - Google Drive Report"
    email['Subject'] = subject
    
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
        raise Exception("An error occurred attempting to connect to your Google Drive. \n",
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
                raise Exception('An error occurred: %s' %error)
                break
    else:
        raise Exception("Service is None")
    logger.debug("Archived drive state loaded successfully.")
    return result

def create_json_file_from_meta(stateJSON):
    archivedGDriveStateFilename = os.path.join(scripthome, "savedState.json")
    try:
        filename = archivedGDriveStateFilename
        with open(filename, 'w') as dst:
            json.dump(stateJSON, dst)
            dst.close()
        print ("Archived PG Drive created.  Thanks!")

    except IOError as (errno, strerror):
        raise
    except:
        raise

def getModifiedFiles(reformatCurrent, reformatArchive):
    modifiedFiles = set([])
    for item in reformatCurrent:
        try:
            reformatArchive[item]
            if reformatArchive[item]["modifiedDate"] != reformatCurrent[item]["modifiedDate"]:
                modifiedFiles.add(item)
        except:
            # Key must not be in reformatArchive so ignore
            pass
    return modifiedFiles
    

def reformatDrive(driveState, pgIDs):
    newDrive = {}
    for item in driveState:
        if item["id"] in pgIDs:
            newDrive[item["id"]] = {"modifiedDate" : item["modifiedDate"]}
    return newDrive         

if __name__ == '__main__':
    main()
