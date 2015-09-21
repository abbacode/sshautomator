#------------------------------
# SSH session, to be tested
#------------------------------
class SSH(object):
    def __init__(self, device_name, username,password, buffer=65535,delay="0.5", port="22"):
        self.device_name = device_name
        self.username = username
        self.password = password
        self.buffer = buffer
        self.delay = delay
        self.port = int(port)
        self.established = False
        self.enable_mode = False
        self.error_msg = ''

    def connect(self):
        import paramiko
        try:
            self.pre_session = paramiko.SSHClient()
            self.pre_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.pre_session.connect(self.device_name,
                                     username=self.username,
                                     password=self.password,
                                     allow_agent=False,
                                     look_for_keys=False,
                                     port=self.port)
            self.session = self.pre_session.invoke_shell()
            self.established = True
            return self.session
        except Exception as ex:
            template = "Error: {0}".format(type(ex).__name__)
            self.error_msg = template

    def close(self):
        return self.pre_session.close()

    def clear_buffer(self):
        if self.session.recv_ready():
            return self.session.recv(self.buffer).decode('UTF-8')
        return None

    @property
    def in_enable_mode(self):
        if '#' in self.command('\n'):
            return True

    def set_enable(self, enable_password):
        if not self.enable_mode:
            self.command('enable')
            self.command(enable_password)
        if self.in_enable_mode:
            self.enable_mode = True

    def prepare_cisco_session(self,device):
        self.clear_buffer()
        self.session.send('term len 0\n')
        self.set_enable(device.enable_pass)

    def command(self, command):
        import time

        self.clear_buffer()
        self.session.send(command + '\n')
        not_done = True
        output = ''
        while not_done:
            time.sleep(float(self.delay))
            if self.session.recv_ready():
                output += self.session.recv(self.buffer).decode('UTF-8')
            else:
                not_done = False
        return output

#------------------------------
# Telnet session to be tested
#------------------------------
class Telnet(object):
    def __init__(self, device_name, username, password, delay="0.5", port="23"):
        self.device_name = device_name
        self.username = username
        self.password = password
        self.delay = float(delay)
        self.port = int(port)
        self.established = False
        self.ready_to_execute = False
        self.error_msg = ''

    def connect(self):
        import telnetlib

        self.session = telnetlib.Telnet(self.device_name, self.port)
        login = self.session.read_until('Username', 3)
        print (login)
        '''
        self.session = telnetlib.Telnet(self.device_name, self.port)
        login_prompt = self.session.read_until(b"\(Username: \)|\(login: \)",self.delay)
        if 'login' in login_prompt.decode('UTF-8'):
            self.is_nexus = True
            self.session.write(self.username + '\n')
        elif 'Username' in login_prompt.decode('UTF-8'):
            self.is_nexus = False
            self.session.write(self.username + '\n')

        password_prompt = self.session.read_until(b'Password:',self.delay).decode('UTF-8')
        self.session.write(self.password + '\n')
        return self.session
        '''

    def close(self):
        return self.access.close()

    def set_enable(self, enable_password):
        import re

        if re.search('>$', self.command('\n')):
            self.access.write('enable\n')
            enable = self.access.read_until('Password')
            return self.access.write(enable_password + '\n')
        elif re.search('#$', self.command('\n')):
            return "Action: None. Already in enable mode."
        else:
            return "Error: Unable to determine user privilege status."

    def disable_paging(self, command='term len 0'):
        self.access.write(command + '\n')
        return self.access.read_until("\(#\)|\(>\)", self.delay)

    def command(self, command):
        self.access.write(command + '\n')
        return self.access.read_until("\(#\)|\(>\)", self.delay)

#----------------------------
# If no session is defined
#----------------------------
class Unknown(object):
    def __init__(self):
        self.error_msg = 'Error: invalid connection type'
        self.established = False

    def connect(self):
        pass