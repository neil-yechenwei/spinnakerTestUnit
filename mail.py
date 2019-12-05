import smtplib, ssl, os

smtp_server = "smtp.office365.com"
port = 587  # For starttls
sender_email = "<insert your sender email>"
receiver_email = "<insert your receiver email>"

password = "<insert your sender email password>"

# Create a secure SSL context
ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

# allow TLS 1.2 and later
ctx.options |= ssl.OP_NO_SSLv2
ctx.options |= ssl.OP_NO_SSLv3
ctx.options |= ssl.OP_NO_TLSv1
ctx.options |= ssl.OP_NO_TLSv1_1

local_path = os.path.expanduser("~/software/spinnakerTestUnit")
local_abstract = os.path.join(local_path, "abstract.log")
with open(local_abstract, 'r') as f:
    abstract = f.read()

message = """\
Subject: Spinnaker Daily Test

{abst}""".format(abst=abstract)
os.remove(local_abstract)

# Try to log in to server and send email
try:
    server = smtplib.SMTP(smtp_server,port)
    server.ehlo() # Can be omitted
    server.starttls(context=ctx) # Secure the connection
    server.ehlo() # Can be omitted
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, message)
except Exception as e:
    # Print any error messages to stdout
    print(e)
finally:
    server.quit()
