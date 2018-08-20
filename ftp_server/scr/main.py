import socketserver
import json
import hashlib
import os,sys
from conf.account import accounts

class MyTCPHandler(socketserver.BaseRequestHandler):
    exit_flag = False
    def handle(self):
        # self.request is the TCP socket connected to the client
        while not self.exit_flag:
            try:
                self.data = self.request.recv(1024).strip()
                print("{} wrote:".format(self.client_address[0]))
                print(self.data)
                msg_dic = json.loads(self.data.decode())
                action = msg_dic['action']
                if hasattr(self,action):
                    func = getattr(self,action)
                    # self.request.send('action comfirm'.encode('utf-8'))
                    func(msg_dic)
                else:
                    self.request.send('action error'.encode('utf-8'))
            except Exception as e:
                print('用户断开')
                break

    def ftp_authentication(self,msg):
        print('authentication start:')
        auth_res = False
        if len(msg) == 3:
            msg_type = msg['action']
            username = msg['username']
            password = msg['password']
            if username in accounts.keys():
                if accounts[username]['passwd'] == password:
                    auth_res = True
                    self.login_user = username
                    self.cur_path = '%s/%s' %(os.path.dirname(__file__),accounts[username]['home'])
                    self.home_path = '%s/%s' %(os.path.dirname(__file__),accounts[username]['home'])
                else:
                    #print '---wrong passwd---'
                    auth_res = False
            else:
                auth_res == False
        else:
            auth_res == False

        if auth_res:
            msg = "%s::success" % msg_type
            print('\033[32;1muser:%s has passed authentication!\033[0m' % username)
        else:
            msg = "%s::failed" % msg_type
        self.request.send(msg.encode('utf-8'))

    def file_transfer(self,*args):
        print('file transfer start:')
        msg_dic = args[0]
        transfer_type = msg_dic['type']
        filename = msg_dic['filename']
        filename = '%s//%s' % (self.cur_path, filename)

        if transfer_type == 'put':
            filesize = msg_dic['filesize']
            dirname = os.path.dirname(filename)
            if os.path.isfile(filename) :
                has_file_size = os.stat(filename).st_size
                if has_file_size == filesize:
                    filename = filename + '.new '
                    response_msg = {"comfirm": True,"status_code":801}
                else: # has_file_size < filesize:
                    response_msg = {"comfirm": True,"status_code":800,"has_file_size":has_file_size}
            elif not os.path.exists(dirname):
                print(dirname)
                os.makedirs(dirname)
                response_msg = {"comfirm": True, "status_code": 802}
            else:
                response_msg = {"comfirm": True, "status_code": 802}
            self.request.send(json.dumps(response_msg).encode('utf-8'))

            f = open(filename, 'wb')
            m = hashlib.md5()
            pre_size = 8096
            recv_size = 0
            while recv_size < filesize:
                if filesize - recv_size > pre_size:
                    temp = self.request.recv(pre_size)
                else:
                    temp = self.request.recv(filesize - recv_size)  # 防止粘包
                f.write(temp)
                m.update(temp)
                recv_size += len(temp)
            print('%s upload done' % filename)
            f.close()

        elif transfer_type == 'get':
            if os.path.isfile(filename):
                file_size = os.path.getsize(filename)
                msg_dic = {
                    "filename": filename,
                    "filesize": file_size,
                    "comfirm": True,
                }
                self.request.send(json.dumps(msg_dic).encode('utf-8'))
                client_confirm_msg = json.loads(self.request.recv(1024).decode())

                if client_confirm_msg['comfirm']==True:
                    start_size = 0
                    if client_confirm_msg['has_file_size']:
                        start_size = client_confirm_msg['has_file_size']
                    f = open(filename,'rb')
                    f.seek(start_size)
                    size_left = file_size-start_size
                    while size_left >0:
                        if size_left < 1024:
                            self.request.send(f.read(size_left))
                            size_left = 0
                        else:
                            self.request.send(f.read(1024))
                            size_left -= 1024
                    print("send file done....")
                    f.close()
                else:
                    return
            else:#file doesn't exist
                msg_dic = {
                    "err_msg": 'file does not exist or is a directory',
                    "comfirm": False,
                }
                self.request.send(json.dumps(msg_dic).encode('utf-8'))

    def has_privilege(self,path):
        abs_path = os.path.abspath(path)
        if abs_path.startswith(os.path.abspath(self.home_path)):
            return True
        else:
            return  False

    def delete_file(self,msg):
        print('-->delete file:',msg['filename'])
        file_list = msg['filename']
        res_list = []
        for i in file_list:
            abs_file_path = "%s/%s" %(self.cur_path,i)
            cmd_res = os.remove(abs_file_path)

    def list_file(self,msg):

        path = self.cur_path
        file_list= os.listdir(path)
        if not file_list:
            file_list="<empty directory>"
        confirm_msg = "message_transfer::ready::%s" % len(file_list)
        self.request.send(confirm_msg.encode('utf-8'))
        confirm_from_client = self.request.recv(100).decode()
        if confirm_from_client == "message_transfer::ready::client":
            self.request.send(' '.join(file_list).encode('utf-8'))

    def switch_dir(self,msg):
        switch_res = ""
        msg = msg['path']
        if len(msg) ==1:# means no dir follows cd cmd, go back to home directory
            self.cur_path = self.home_path
            relative_path = self.cur_path.split(self.home_path)[-1]
            switch_res = "switch_dir::ok::%s" % relative_path
        elif len(msg) == 2:
            path = "%s/%s" % (self.cur_path, msg[1])
            if self.has_privilege(path):
                if os.path.isdir("%s/%s" %(self.cur_path,msg[1])):
                    abs_path = os.path.abspath("%s\%s" %(self.cur_path,msg[1]))
                    if abs_path.startswith(os.path.abspath(self.home_path)):#need to make user can only access to the home path level
                        self.cur_path = abs_path
                        print(abs_path,self.home_path)
                        relative_path = self.cur_path.split(os.path.abspath(self.home_path))[-1]
                        switch_res = "switch_dir::ok::%s" % relative_path
                    else:
                        switch_res = "switch_dir::error::target dir doesn't exist"
                else:
                    os.makedirs(path)
                    abs_path = os.path.abspath("%s/%s" % (self.cur_path, msg[1]))
                    self.cur_path = abs_path
                    relative_path = self.cur_path.split(self.home_path)[-1]
                    switch_res = "switch_dir::ok::%s" % relative_path
            else:
                switch_res = "switch_dir::error::target dir doesn't belong to you"
        else:
            switch_res = "switch_dir::error::Error:wrong command usage."
        self.request.send(switch_res.encode('utf-8'))

    def mkdir(self,msg):
        print("create new dir")
        path = msg.get("path")
        tar_path=os.path.join(self.cur_path,path)
        if not os.path.exists(tar_path):
            if "/" in path:
                os.makedirs(tar_path) #创建多级目录
            else:
                os.mkdir(tar_path) #创建单级目录
            self.request.send(b"mkdir_success!")
        else:
            self.request.send(b"dir_exists!")

    def rmdir(self,msg):
        print("remove dir")
        path = msg.get("path")
        print(path)
        tar_path=os.path.join(self.cur_path,path)
        if os.path.exists(tar_path):
            print(111)
            if os.path.isfile(tar_path):
                print(222)
                os.remove(tar_path) #删除文件
            elif "/" in path:
                print(333)
                os.removedirs(tar_path) #删除目录
            else:
                print(111)
                os.rmdir(tar_path)
            self.request.send(b"rm_success!")
        else:
            self.request.send(b"the file or dir does not exist!")

if __name__ == "__main__":
    HOST, PORT = "localhost", 6969
    # Create the server, binding to localhost on port 9999
    # server = socketserver.TCPServer((HOST, PORT), MyTCPHandler)
    server = socketserver.ThreadingTCPServer((HOST, PORT), MyTCPHandler)
    # server = socketserver.ForkingTCPServer((HOST, PORT), MyTCPHandler)
    server.serve_forever()