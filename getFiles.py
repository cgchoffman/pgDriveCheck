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

import shutil
import urllib2
import urllib
import sys
import os
import logging

logger = logging.getLogger('PG-Backup')

def write_file(content, filename, datebackuppath):
    # 'home' should work on any platform.  OSX not checked.
    #home = os.getenv('USERPROFILE') or os.getenv('HOME')
    #path = os.path.join(home, "driveBackup", date)
    ensure_dir(datebackuppath)
    # append filename to path
    filepath = os.path.join(datebackuppath, filename)
    #XXX added 'b' option to help handling of binary files like pitures
    try:
        with open(filepath, 'wb') as dst:
            dst.write(content)
    except Exception as  e:
        error = """Could not write file to disk: %s. 
        Error: %s""" %(fileJSON['title'], e)
        logger.warning(error)
        raise Exception(error)
    


def download_file(service, download_url):
    """Download a file's content.  Returns content and filename

    Args:
      service: Drive API service instance.
      drive_file: Drive File instance.

    Returns:
      File's content if successful, None otherwise.
    """
    #download_url = drive_file.get('downloadUrl')
    resp, content = service._http.request(download_url)
    if resp.status == 200:
        filename = resp['content-disposition'][resp['content-disposition'].find("=")+2:resp['content-disposition'].find('"',resp['content-disposition'].find("=")+2)]
        logger.debug("Starting download of %s", filename)
        filename = urllib.unquote(filename.encode("utf8"))
        logger.debug("Downloaded %s successfully", filename)
        return content, filename
    else:
        logger.warning("Could not download %s.", fileJSON['title'])
        raise Exception("File failed to download.")

def get_download_url(fileJSON):
    """ Get the link that can download the file
    """
    try:
        return fileJSON.get('downloadUrl')
    except Exception as e:
        print e
        print "no download url found for %s" %(fileJSON['title'])
        print "Here's some additional information for you:"

        for i in fileJSON:
            print ("  %s is: %s" %(i,fileJSON[i]))
        return None

def get_export_link(file):
    # Not all file objects have an exportLink it seems
    fileName = file['title']    
    ext =  fileName[len(fileName)-fileName[::-1].find('.'):] #returns file extension
    print ext, fileName
    exportLinks = file.get('exportLinks')
    if exportLinks != None:
        if ext == '':
            try:
                link = exportLinks.get('application/vnd.oasis.opendocument.text')
                return link
            except Exception as e:
                logging.warn("No odt format for file %s.", fileName)
        for key in file['exportLinks']:
            if file['exportLinks'][key].find('=%s'%ext)>-1:
                return file['exportLinks'][key]
        return file['exportLinks'].popitem()[1]
    # If you've made it this far, something went wrong and you
    # aren't going to download anything.
    logging.warn("%s file was not downloaded.", fileName)

def ensure_dir(path):
    """ Make sure the path exist that you're writing to
    """
    #d = os.path.dirname(path)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception as e:
            return e
