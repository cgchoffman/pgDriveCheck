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

def write_file(content, filename, date):
    # 'home' should work on any platform.  OSX not checked.
    home = os.getenv('USERPROFILE') or os.getenv('HOME')
    path = os.path.join(home, "driveBackup", date)
    ensure_dir(path)
    # append filename to path
    path = os.path.join(path, filename)
    #XXX added 'b' option to help handling of binary files like pitures
    try:
        with open(path, 'wb') as dst:
            dst.write(content)
    except Exception as  e:
        raise e
    


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
        raise "File failed to download."
        return None

def get_export_link(fileJSON):
    """Get the exportLink value from the file object
    Not all fileJSON objects have an exportLink it seems
    """

    fileName = fileJSON['title']
    ext =  fileName[len(fileName)-fileName[::-1].find('.'):] #returns fileJSON extension
    for key in fileJSON['exportLinks']:
        if fileJSON['exportLinks'][key].find('=%s'%ext)>-1:
            return fileJSON['exportLinks'][key]
    return fileJSON['exportLinks'].popitem()[1]

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
        logger.warning("Could not download %s.", fileJSON['title'])

def ensure_dir(path):
    """ Make sure the path exist that you're writing to
    """
    #d = os.path.dirname(path)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception as e:
            return e
