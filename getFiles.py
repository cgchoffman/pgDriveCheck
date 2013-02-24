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

def main(service, jsonedFiles):

    try:
        number_of_files_to_download = 1 # Number of files to dl, set -1 for all.
        allFiles = files[:]

        for file in allFiles:
            number_of_files_to_download -= 1
            if number_of_files_to_download == 0:
                break
            try:
                if file['mimeType'].find("folder") > -1: # It's not a file, skip it
                    continue
                dFile = get_export_link(file)
            except KeyError: # Some files don't have an export link
                try:
                    dFile = file['downloadUrl']
                except KeyError: # Some files don't have a downloadUrl
                    try:
                        dFile = file['webContentLink']
                    except KeyError: # Some files don't have a webContentLink...now we're screwed.
                        print "no download url found"
                        failed.append(file)
                        continue
            except Exception as e:
                print "something went wrong with a file. Will skip and continue.", e
                continue
            content, filename = download_file(service, dFile)
            # 'home' should work on any platform.  OSX not checked.
            home = os.getenv('USERPROFILE')  or os.getenv('HOME')
            path = "%s/driveBackups/%s"%(home,filename)
            ensure_dir(path)
            with open(path, 'w') as dst:
                dst.write(content)

    except AccessTokenRefreshError:
        # The AccessTokenRefreshError exception is raised if the credentials
        # have been revoked by the user or they have expired.
        print ('The credentials have been revoked or expired, please re-run'
               'the application to re-authorize')
    print len(failed)
    print failed
    download_file()

def load_json_file(jsonFile):
    with open(jsonFile, 'r') as fileData:
        jsonData = json.loads(fileData.read())
        fileData.close()
    return jsonData

def download_file(service, download_url):
    """Download a file's content.

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

def retrieve_all_meta_files(service):
    """Retrieve a list of File resources.

    Args:
      service: Drive API service instance.
    Returns:
      List of File resources.
    """
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
            print 'An error occurred: %s' % error
            break
    return result

def get_export_link(file):
    # Not all file objects have an exportLink it seems
    fileName = file['title']
    ext =  fileName[len(fileName)-fileName[::-1].find('.'):] #returns file extension
    print ext, fileName
    for key in file['exportLinks']:
        if file['exportLinks'][key].find('=%s'%ext)>-1:
            return file['exportLinks'][key]
    return file['exportLinks'].popitem()[1]



def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        try:
            os.makedirs(d)
        except Exception as e:
            return e

if __name__ == '__main__':
    main()

