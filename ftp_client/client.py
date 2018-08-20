import socket
import os
import json
import hashlib
import getpass
import sys

status_code  = {
    250 : "Invalid cmd format, e.g: {'action':'get','filename':'test.py','size':344}",
    251 : "Invalid cmd ",
    252 : "Invalid auth data",
    253 : "Wrong username or password",
    254 : "Passed authentication",

    800 : "the file exist,but not enough ,is continue? ",
    801 : "the file exist !",
    802 : " ready to receive datas",

    900 : "md5 valdate success"

}
func_dic = {
    'help': 'help',
    'get': 'get_file',
    'put': 'put_file',
    'exit': 'exit',
    'ls': 'list_file',
    'cd': 'switch_dir',
    'del': 'delete',
    'mkdir': 'makedir',
    'rm':'rmdir'
}

class Ftpclient(object):

    def __init__(self,ip,port):
        self.sock = socket.socket()
        self.sock.connect((ip,port))
        self.exit_flag = False
        if self.auth():
            self.interactive()

    def help(self,*args):
        help_text = """
            'help'  'some help text about how to use',
            'get'  'download a file following by a filename',
            'put'  'upload a file following by a filename',
            'exit'  'exit the program',
            'ls'  'list all file in current path',
            'cd'  'switch path:/xx/xx/',
            'del' 'delete a file following by a filename'
       """
        print(help_text)

    def interactive(self):
        try:
            while not self.exit_flag:
                msg = input("[\033[;32;1m%s|\033[0m%s]>>:" % (self.username,self.cur_path) ).strip()
                if len(msg) == 0: continue  # 不卡住
                cmd_parse = msg.split()
                cmd = cmd_parse[0]
                if hasattr(self,func_dic[cmd]):
                    func = getattr(self,func_dic[cmd])
                    func(cmd_parse)
                else:
                    print("Invalid instruction,type [help] to see available cmd list")
        except KeyboardInterrupt:
            self.exit()
        except EOFError:
            self.exit()

    def exit(self,*args):
        self.sock.shutdown(socket.SHUT_WR)
        sys.exit("Bye! %s" % self.username)

    def put_file(self,*args):
        cmd_list = args[0]
        if len(cmd_list)==2:
            filename = cmd_list[1]
            if os.path.isfile(filename):
                print('找到本地文件，开始建立连接')
                file_size = os.stat(filename).st_size
                msg_dic = {
                    "action":'file_transfer',
                    "filename":filename,
                    "filesize":file_size,
                    "overridden":True,
                    'type':'put'
                }
                self.sock.send(json.dumps(msg_dic).encode('utf-8'))
                server_response = self.sock.recv(1024).decode()
                print(server_response)
                response = json.loads(server_response)

                if response['comfirm']==True and response['status_code'] == 802:
                    print('连接成功，开始上传')
                    sent_size = 0
                elif response['comfirm']==True and response['status_code'] == 801:
                    print('连接成功，服务器文件已存在，将另名')
                    sent_size = 0
                elif response['comfirm']==True and response['status_code'] == 800:
                    print('连接成功，文件已部分上传，本次续点上传')
                    sent_size = response['has_file_size']
                else:
                    print('连接失败')
                    return
                f = open(filename, 'rb')
                f.seek(sent_size)
                while not sent_size == file_size:
                    if file_size - sent_size <= 8096:
                        data = f.read(file_size - sent_size)
                        sent_size += file_size - sent_size
                    else:
                        data = f.read(8096)
                        sent_size += 8096
                    self.sock.send(data)
                    self.show_progress_percent(sent_size, file_size)
                print('file upload done')
                f.close()
            else:
                print('no file')
        else:
            self.help()

    def get_file(self,*args):
        cmd_list = args[0]
        if len(cmd_list) == 2: # get remote_filename
            filename = cmd_list[1]
            msg_dic = {
                "action": 'file_transfer',
                "filename": filename,
                "overridden": True,
                'type': 'get'
            }
            self.sock.send(json.dumps(msg_dic).encode('utf-8'))
            feedback = self.sock.recv(1024).decode()
            response = json.loads(feedback)
            if response['comfirm']:
                filesize = response['filesize']
                filename = os.path.basename(cmd_list[1])

                if os.path.isfile(filename):
                    has_file_size = os.stat(filename).st_size
                    if has_file_size == filesize:
                        choice = input("the file exist ,is_continue? Y/N").strip()
                        if choice.upper() == "Y":
                            filename = filename + '.new '
                            response_msg = {"comfirm": True, "status_code": 801}
                        else:
                            print("cancel download file......")
                            response_msg = {"comfirm": False}
                            self.sock.send(json.dumps(response_msg).encode('utf-8'))
                            return
                    else:  # has_file_size < filesize:
                        response_msg = {"comfirm": True, "status_code": 800, "has_file_size": has_file_size}
                else:
                    response_msg = {"comfirm": True, "status_code": 802}

                self.sock.send(json.dumps(response_msg).encode('utf-8'))
                f = open(filename, 'wb')
                size_recv = 0
                while size_recv < filesize:
                    data = self.sock.recv(1024)
                    size_recv += len(data)
                    f.write(data)
                    self.show_progress_percent(size_recv,filesize)
                print("recieved the file done")
                f.close()
            else:#file doesn't exist on remote or sth else went wrong.
                print('\033[31;1m%s\033[0m' %response['err_msg'])

    def show_progress_percent(self,current, total):
        rate = float(current) / float(total)
        rate_num = int(rate * 100)
        progress_mark = "=" * int(rate_num / 3)
        print("[%s/%s]%s>%s%%\r" % (total, current, progress_mark, rate_num))

    def delete(self, msg):
        if len(msg) > 1:
            msg_dic = {
                "action": 'delete_file',
                "filename": msg[1:],
            }
            self.sock.send(json.dumps(msg_dic).encode('utf-8'))
        else:
            print("\033[31;1mWrong command usage\033[0m")

    def list_file(self,msg):
        msg_dic = {
            "action": 'list_file',
        }
        self.sock.send(json.dumps(msg_dic).encode('utf-8'))
        server_confirm_msg = self.sock.recv(100).decode()
        if server_confirm_msg.startswith("message_transfer::ready"):
            server_confirm_msg = server_confirm_msg.split("::")
            msg_size = int(server_confirm_msg[-1])
            self.sock.send("message_transfer::ready::client".encode('utf-8'))
            data = self.sock.recv(1024)
            print(data.decode())

    def switch_dir(self, msg):
        msg_dic = {
            "action": 'switch_dir',
            'path': msg
        }
        self.sock.send(json.dumps(msg_dic).encode('utf-8'))
        feedback = self.sock.recv(100).decode()
        if feedback.startswith("switch_dir::ok"):
            self.cur_path = feedback.split("::")[-1]
        else:
            print("\033[31;1m%s\033[0m" % feedback.split("::")[-1])

    def makedir(self,msg):
        msg_dic = {
            "action": 'mkdir',
            'path': msg[1]
        }
        self.sock.send(json.dumps(msg_dic).encode())
        data = self.sock.recv(1024)
        print(data.decode("utf8"))

    def rmdir(self,msg):
        msg_dic = {
             'action':'rmdir',
             'path':msg[1]
        }
        self.sock.send(json.dumps(msg_dic).encode())
        data = self.sock.recv(1024)
        print(data.decode("utf8"))

    def auth(self):
        retry_count = 0
        while retry_count < 3:
            username = input("username:").strip()
            if len(username) == 0: continue
            # passwd = getpass.getpass('password:')
            passwd = input("password:").strip()
            msg_dic = {
                'action':'ftp_authentication',
                'username':username,
                'password':passwd
            }
            self.sock.send(json.dumps(msg_dic).encode('utf-8'))
            auth_feedback = self.sock.recv(1024).decode()

            if auth_feedback == "ftp_authentication::success":
                print("\033[32;1mAuthentication Passed!\033[0m")
                self.username = username
                self.cur_path = username
                return True
            else:
                print("\033[31;1mWrong username or password\033[0m")
                retry_count += 1
        else:
            print("\033[31;1mToo many attempts,exit!\033[0m")


if __name__ == "__main__":
    f = Ftpclient('localhost', 6969)




























