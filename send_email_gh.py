#!/usr/bin/env python3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

gmail = 'mohdalizahoor@gmail.com'
app_pass = 'qlwblerbnwomowna'
send_to = 'mohdalizahoor@gmail.com'

msg = MIMEMultipart()
msg['From'] = gmail
msg['To'] = send_to
msg['Subject'] = '360dialog Partner Docs - Daily Check Complete'

body = '''360dialog Partner Docs Check
================================

Status: Completed successfully

The daily check has finished.
View log in GitHub Actions.

---
Automated from GitHub Actions
'''
msg.attach(MIMEText(body, 'plain'))

server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login(gmail, app_pass)
server.sendmail(gmail, send_to, msg.as_string())
server.quit()
print('Email sent')