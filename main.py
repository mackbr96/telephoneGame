import socket  # socket library
import sys
import platform
import datetime
from collections import OrderedDict
from random import randint
import re
import requests
# checking the number of arguments: name, origin, IP, port

if len(sys.argv) != 4:
    print('invalid number of arguments, should be four')
    sys.exit(1)

# all commandline arguments are strings & need to be casted to be compared to ints
origin = int(sys.argv[1])
ip = sys.argv[2]
port = int(sys.argv[3])

# for being the originator, should be 1 & for non originator should be 0
if origin not in [0, 1]:
    print('Pick 0 or 1 for being origin or not')
    sys.exit(1)
else:
    origin = True if (origin == 1) else False

EOM = "\r\n.\r\n"
STARTING_MESSAGE = "Hello! You're receiving a message from the telephone game!" + EOM

SUCCESS = "SUCCESS"
WARN = "WARN"
GOODBYE = "GOODBYE"

# -----------------------------------------------------------------------------------

# Handshake function for both client and server
def handshake(connection, client=True, message="HELLO 1.7"):
    if (client):
        data = connection.recv(1024).decode()
        if (data != message):
            connection.send("QUIT".encode())
            data = connection.recv(1024).decode()

            if (data == GOODBYE):
                return False
        else:
            connection.send(message.encode())
            return True
    else:
        connection.send(message.encode())
        data = connection.recv(1024).decode()

        if (data != message):
            connection.send(GOODBYE.encode())
            return False
        else:
            return True


def addHeaders(message=""):
    lines =  message.split('\r\n')

    headers = OrderedDict()
    headers["Hop"] = "0" if origin else str(int((lines[0].split())[1]) + 1)
    headers["MessageId"] = str(randint(0, 8999) + 1000) if origin else (lines[1].split())[1]
    # Need to fix FromHost. Returns Loopback address
    headers["FromHost"]  = requests.get('http://ip.42.pl/raw').text
    headers["ToHost"] = ip
    headers["System"] = platform.system() + platform.release()
    headers["Program"] = "Python 3"
    headers["Author"] = "Jake Nesbitt, Ben Mack"
    headers["SendingTimestamp"] = str(datetime.datetime.now())
    headers["MessageChecksum"] = computeMessageCheckSum(message)

    # if not origin:
    #     headers["HeadersChecksum"] = computeHeaderCheckSum(message)

    newHeaders = ''
    for i, v in headers.items():
        newHeaders = newHeaders + i + ": " + v + '\r\n'

    return newHeaders + ("\r\n" if origin else "") + message

# define the server side
def server_func():
    # IP address & port number, '' specifies that the socket is reachable by any address the machine happens to have.
    host = ''

    s = socket.socket()

    # allow this socket to be "reused" if it's still in CLOSE_WAIT from a killed previous instance
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # bind takes a tuple of a host address & port number
    s.bind((host, port))

    # starts listening for TCP connections. We want to listen for connections.
    s.listen(5)

    # accepts a connection when found. c for the connection & addr for the address.
    c, addr = s.accept()

    print("Connection From Server: " + str(addr))

    if (not handshake(c, False)):
        s.close()
        print("HANDSHAKE FAILED")

        return False
    else:
        print("HANDSHAKE SUCCESSFUL")

    dataMessage = c.recv(1024).decode()

    receivedData = ''
    while True:
        data = c.recv(1024).decode()

        if not data:
            break
        else:
            receivedData = data if (receivedData == '') else receivedData + data

        if (EOM in data):
            break

    # Check checksum of data, and send back SUCCESS or WARN
    if (receivedData != '' and validateMessageCheckSum(receivedData)):
        c.send(SUCCESS.encode())
    else:
        c.send(WARN.encode())

    # Wait for QUIT from client
    while (c.recv(1024).decode() != "QUIT"):
        continue

    c.send(GOODBYE.encode())
    c.close()

    return receivedData

# ------------------------------------------------------------------------------------------

# define the client side
def client_func(message = STARTING_MESSAGE):
    # create a socket object s
    s = socket.socket()

    # try connecting to the server
    s.connect((ip, port))

    if (not handshake(s)):
        s.close()
        print("RECIEVED INVALID RESPONSE FROM SERVER")
        sys.exit()

    # Untested
    s.send("DATA".encode())
    s.send(addHeaders(message).encode())

    # Waiting for Success or Warn
    while (s.recv(1024).decode() not in [SUCCESS, WARN]):
        continue

    s.send("QUIT".encode())

    # Waiting for GOODBYE
    while (s.recv(1024).decode() != GOODBYE):
        continue

    s.close()

# --------------------------------------------------------------------------------------------

# def checksum(data):
#     if (type(data) != bytes):
#         data = str.encode(data)

#     if len(data) & 1:
#         data=data + b'\0'
#     sum=0
#     for i in range(0, len(data), 2):
#         sum += data[i] + (data[i + 1] << 8)
#     while (sum >> 16) > 0:
#         sum=(sum & 0xFFFF) + (sum >> 16)
#     return format(~sum, 'x')

# New checksum
def checksum(bt):
    if not isinstance(bt, bytes):
        bt = str.encode(bt)

    tobyte = ord
    if isinstance(bt[0], int):  # Python 3
        tobyte = lambda x: x

    sum = 0
    for i in range(len(bt)):
        sum += tobyte(bt[i]) << (0 if i&1 else 8)

    while (sum >> 16):
        sum = (sum & 0xFFFF) + (sum >> 16)

    #Added padding
    answer = format(((~sum) & 0xFFFF), 'x')
    while(len(answer) < 4):
        answer = '0' + answer
    return answer
    # return format(((~sum) & 0xFFFF), 'x')

def computeMessageCheckSum(message):
    # Get rid of EOM
    body = message.split("\r\n.\r\n")
    body = body[0]

    if ("\r\n\r\n" in body):
        body = body.split("\r\n\r\n")[1]
    return checksum(body)

def validateMessageCheckSum(message):
    lines =  message.split('\r\n')
    actualChecksum = ([x for x in lines if ("MessageChecksum" in x)][0]).split()[1]
    computedChecksum = computeMessageCheckSum(message)

    return (computedChecksum == actualChecksum)


def computeHeaderCheckSum(message):
    headers = message.split("\r\n")
    #Untested
    hops = [i for i in range(len(headers)) if re.match(r'Hop: \d*', headers[i])]
    headers = headers[1:]
    # headers = headers[0] + "\r\n"

    #Join headers into sngle string then pass
    return checksum(headers)

def validateHeaderCheckSum(message):
    lines =  message.split('\r\n')
    actualChecksum = [x for x in lines if ("HeadersChecksum" in x)]  #[0] # .split()[1]

    if (len(actualChecksum) < 1):
        return True

    actualChecksum = actualChecksum[0].split()[1]
    computedChecksum = computeHeaderCheckSum(message)

    return (computedChecksum == actualChecksum)

# -- Run --
if origin:
    client_func()
    print("Received message!\r\n----\r\n" + server_func())
else:
    serverResult = server_func()
    if (serverResult):
        print("Received message!\r\n----\r\n" + serverResult)
        client_func(serverResult)

