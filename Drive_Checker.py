#!/usr/bin/env python
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

class DriverChecker(object):
    def __init__(self):
        self.scripthome = os.getcwd()
        self.loghome = os.path.join(self.scripthome, "PGbackups.log") # Logs home
        self.home = os.getenv('USERPROFILE') or os.getenv('HOME')
        self.backuppath = os.path.join(self.home, "driveBackup")
        self.corepath = os.path.join(self.backuppath,"core")
        self.date = datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.datebackuppath = os.path.join(self.backuppath, self.date)
        self.create_logger()
        ## XXX These two or more need error checking so they don't crash if
        # something can't be loaded.
        self.configData = cfc.load_json_file("config.json")
        self.credentials = cfc.get_credentials(configData)
        self.service = cfc.get_service(credentials)
        self.currentGDriveState = cfc.retrieve_all_meta(service)
        ### XXX        
    
    # Valid log levels:
    #   -CRITICAL	50
    #   -ERROR	    40
    #   -WARNING	30
    #   -INFO	    20
    #   -DEBUG	    10
    #   -NOTSET     0 
    def set_log_level(self, level):
        self.log.setLevel(level)
    
    def create_logger(self):
        logging.basicConfig(format='%(levelname)s:[%(asctime)-15s]: %(funcName)s: %(message)s\n\t%(exc_info)s',
            filemode='w', filename=loghome, level=logging.INFO)
        self.log = logging.getLogger('PG-Backup')
    
    # Just download all the files that are there.  Don't check for changes.
    def dwnld_all_files(self, googleDrJson):
        for GDriveObject in googleDrJson:
            if GDriveObject['mimeType'].find('folder') == -1:
                dFile = {}
                if getFiles.get_download_url(GDriveObject) != None:
                    dFile = getFiles.get_download_url(GDriveObject)
                else:
                    dFile = getFiles.get_export_link(GDriveObject)
                filename = ""
                content = ""
                try:
                    content, filename = getFiles.download_file(service, dFile)
                except Exception as e:
                    pass # until you fix the RAISE sissue in getFiles
                    #logger.error("%s: ERROR: %s", GDriveObject['title'], e)
                # if this failed filename will be blank and an error was logged in logs
                if filename != "":
                    try:
                        getFiles.write_file(content, filename, datebackuppath)
                        succDnLds += 1
                        logger.debug("Downloaded and saved %d files. Retrieved: %s", succDnLds, filename)
                    except Exception as e:
                        pass #until you figure out why the raise doesn't work
                        #raise in getfile.
                        #logger.error("""Failed to write the file, %s: ERROR: %s""", filename, e)
    
    #initially get the ID of Share PeaceGeeks folder
    def get_Share_Peace_Id(self, folderData):
        geekFolderIds = []
        for item in folderData:
            if item['title'] == "Shared PeaceGeeks" or item['title'] == "PeaceGeeks Drive":
                geekFolderIds.append(item.get('id'))
                folderData.remove(item)
                break
        return set(geekFolderIds)
    
    def create_list_of_files(self, idSet, jsonState):
        jsonStateCopy = jsonState[:]
        for item in jsonStateCopy:
            if item['id'] not in idSet:
                jsonStateCopy.remove(item)
        return jsonStateCopy
    
    
    # Loop through jsonState looking for folders which have a parent id under the Shared PeaceGeeks
    # hierarchy.  When the list geekFolderIds stops growing then stop the loop.
    def get_all_pg_folder_ids(self, jsonState):
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
    def get_file_id_set(self, jsonState, listOfIds):
        idSet = set()
        if None != jsonState:
            for file in jsonState:
                if file['mimeType'].find('folder') == -1 and file["parents"] and file["parents"][0]["id"] in listOfIds:
                #for item in file["parents"]:
                #    if item[0]["id"] in listOfIds:
                    idSet.add(file["id"])
                        #currentFileIDs[hashlib.sha224(file["id"]).hexdigest()] = file["id"]
        return idSet
    
    def get_difference(self, setOne, setTwo):
        diff = setOne.difference(setTwo)
        return diff
    
    def get_title_owner(self, message, ids, state):
        for file in state:
            if file["id"] in ids:
                # convert owner names away from unicode to a byte string
                filename = file["title"]
                owner = [name.encode("UTF-8") for name in file["ownerNames"]]
                createdDate = file['createdDate']
                message += "File name: %s\nFile Owner: %s\nCreated: %s\n\n" %(filename, owner, createdDate)
        return message
    
    def generate_added_removed_modifed_message(self, removedFileIDs, addedFileIDs, archivedGDriveState, currentGDriveState, modifiedIDs):
        message = "=== Files Removed ===\n"
        message = get_title_owner(message, removedFileIDs, archivedGDriveState)
        message += "\n=== Files Added ===\n"
        message = get_title_owner(message, addedFileIDs, currentGDriveState)
        message += "\n===Modfied Files===\n"
        message = get_title_owner(message, modifiedIDs, currentGDriveState)
        return message
    
    def send_email(self, message, configData, error):
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
    
    def load_json_file(self, jsonFile):
        with open(jsonFile, 'r') as fileData:
            jsonData = json.loads(fileData.read())
            fileData.close()
        return jsonData
    
    def get_credentials(self, configData):
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
            self.log.debug("Credentials retrieved successfully.")
        return credentials
    
    def get_service(self, credentials):
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
            self.log.debug("Service retrieved successfully from Google.")
        except httplib2.ServerNotFoundError, httpError:
            # XXX this raise doesnt work at all
            raise ("An error occurred attempting to connect to your Google Drive. \n",
            "Check that you are conntected to the internet.", httpError)
        return service
    
    def retrieve_all_meta(self, service):
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
        self.log.debug("Archived drive state loaded successfully.")
        return result
    
    def create_json_file_from_meta(self, stateJSON):
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
    
    def getModifiedFiles(self, reformatCurrent, reformatArchive):
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
        
    
    def reformatDrive(self, driveState, pgIDs):
        newDrive = {}
        for item in driveState:
            if item["id"] in pgIDs:
                newDrive[item["id"]] = {"modifiedDate" : item["modifiedDate"]}
        return newDrive         