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
import sys
import os

def write_file(content, filename):
    # 'home' should work on any platform.  OSX not checked.
    home = os.getenv('USERPROFILE') or os.getenv('HOME')
    os.getenv()
    path = "%s/driveBackups/%s"%(home,filename)
    ensure_dir(path)
    with open(path, 'w') as dst:
        dst.write(content)


def download_file(service, download_url):
    """Download a file's content.  Returns content and filename

    Args:
      service: Drive API service instance.
      drive_file: Drive File instance.

    Returns:
      File's content if successful, None otherwise.
    """
    #download_url = drive_file.get('downloadUrl')
    if download_url:
        resp, content = service._http.request(download_url)
        if resp.status == 200:
            filename = resp['content-disposition'][resp['content-disposition'].find("=")+2:resp['content-disposition'].find('"',resp['content-disposition'].find("=")+2)]
            filename = urllib.unquote(filename.encode("utf8"))
            return content, filename
        else:
            print 'An error occurred: %s' % resp
            return None
    else:
        # The file doesn't have any content stored on Drive.
        return "The file doesn't have any content stored on Drive."

def get_export_link(fileJSON):
    """Get the exportLink value from the file object
    Not all fileJSON objects have an exportLink it seems
    This function could be hidden but i dunno how :(  I learn later.  No
    internets right now."""
    
    fileName = fileJSON['title']
    ext =  fileName[len(fileName)-fileName[::-1].find('.'):] #returns fileJSON extension
    print ext, fileName
    for key in fileJSON['exportLinks']:
        if fileJSON['exportLinks'][key].find('=%s'%ext)>-1:
            return fileJSON['exportLinks'][key]
    return fileJSON['exportLinks'].popitem()[1]

def get_download_url(fileJSON):
    """ Get the link that can download the file
    """
    try:
        dFile = get_export_link(fileJSON)
        return dFile
    except KeyError: # Some fileJSONs don't have an export link
        try:
            dFile = fileJSON['downloadUrl']
            return dFile
        except KeyError: # Some fileJSONs don't have a downloadUrl
            try:
                dFile = fileJSON['webContentLink']
                return dFile
            except KeyError: # Some fileJSONs don't have a webContentLink...now we're screwed.
                print "no download url found"
                return None

def ensure_dir(path):
    """ Make sure the path exist that you're writing to
    """
    d = os.path.dirname(f)
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except Exception as e:
            return e
