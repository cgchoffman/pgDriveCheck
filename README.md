pgDriveCheck
============

This is a in-house PeaceGeeks project to maintain a certain level of peace of mind when allowing large groups to use one Google drive.

This code will not run as is.  API keys and auth tokens have been removed store externally to the repo.
The script automatically opns a browser and asks you to allow the script to use your account creds to
  access Google Drive.
the README with information about setting that up yourself to use the Google Drive API.  

Install Google-api-python-client from http://code.google.com/p/google-api-python-client/downloads/list
Others: https://developers.google.com/drive/downloads

May need to up gFlags apparently: sudo easy_install --upgrade python-gflags

Maybe sure you get your CLIENT ID and CLIENT SECRET: https://developers.google.com/drive/quickstart-python#step_1_enable_the_drive_api

This script loads those from a config.json file eg. 
{
   "TOREPORT":[
      "carey@peacegeeks.org",
   ],
   "TOERROR":[
      "carey@peacegeeks.org"
   ],
   "FROM":"security@peacegeeks.org",
   "CLIENTID":"clientID.apps.googleusercontent.com",
   "CLIENTSECRET":"client secret string"
}

You must authenticate yourself first and get a credentials.dat file...I don't remember 
how I got that file right off the top of my head.  I'll try to remember to do that later ;)

I do'nt even need to actually add this sentense...at all.



