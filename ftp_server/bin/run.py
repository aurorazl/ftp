import socketserver
import os,sys

BASE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from scr.main import MyTCPHandler
from conf import settings

HOST, PORT = settings.IP, settings.PORT
# Create the server, binding to localhost on port 9999
# server = socketserver.TCPServer((HOST, PORT), MyTCPHandler)
server = socketserver.ThreadingTCPServer((HOST, PORT), MyTCPHandler)
# server = socketserver.ForkingTCPServer((HOST, PORT), MyTCPHandler)
server.serve_forever()