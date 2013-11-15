#!/usr/bin/env python
# need to integrate this back into the code.
# create email object then send_email()
class pgEmail(errEmailAddrList, reportEmailAddrList, sentFromAddr):
    # should i have an def __init__ t- contruct the object?
    def __init__(self, errEmailAddrList, reportEmailAddrList, sentFromAddr):
        #import email MIMEText to hold the unicode?  I guess
        import email.mime.multipart as parts
        self.emailParts = parts.MIMEMultipart()
        self.toErr = errEmailAddrList
        self.toReport = reportEmailAddrList
        self.from = sentFromAddr

    def send_email(self, message, error)
        import smtplib
        email = _create_email(message)
        SERVER = "localhost"
        server = smtplib.SMTP(SERVER)
        if error:
            TO = self.toErr
        else:
            TO = self.toReport
        server.sendmail(self.from, TO, email.as_string())
        server.quit()

        """
        message is the concantinated text of the work performed by this script.
                logs are the stdout and stderr for the script, it the full system path

         to the log file
        """ 
    def _create_email(self):
        # Convert the Unicode objects to UTF-8 encoding
        TO = [address.encode('utf-8') for address in self.TO]
        email = self.emailParts
        email['To'] = ','.join(e for e in TO)
        email['From'] = self.from
        email['Subject'] = "PeaceGeeks Server - Google Drive Report"
        import email.mime.text as text
        body = text.MIMEText(message, _charset='utf-8')
        email.attach(body)
        # Attach log file to the email
        #attachFile = open(logs, 'r')
        attachFile = text.MIMEText(open(logs, 'r').read(), _charset='utf-8')
        attachFile.add_header('Content-Disposition', 'attachment',
                              filename=logs)           
        email.attach(attachFile)
        return email
    