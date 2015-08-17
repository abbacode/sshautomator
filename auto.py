__version__ = 2.0

import xlrd
import paramiko
import time
import socket
import sys

class Database(object):
    def __init__(self):
        self.devices = {}
        self.tasks = {}

class Device(object):
    def __init__(self):
        self.hostname = ''
        self.ipaddress = ''
        self.username = ''
        self.password = ''
        self.enable_pass = ''
        self.platform = 'cisco'

class Task(object):
    def __init__(self):
        self.no = '-1'
        self.description = ''
        self.enabled = False
        self.target = {}
        self.cmds = []
        self.delay = ''
        self.buffer = ''
        self.filename = ''
        self.status = {}
        self.devices = {}

class Output(object):
    def __init__(self):
        self.cmd_output = {}

#----------------------------------------------------------------
# Initalise empty database to capture raw spreadsheet data
#-----------------------------------------------------------------
DATA = {}       #raw_data read from the file

#----------------------------------------------------------------
# Read information from the database.xlsx
# Information will be stored by worksheet name, row, column name
#-----------------------------------------------------------------
def read_database_from_file(filename):
    try:
        wb = xlrd.open_workbook(filename)
    except:
        print ('Cannot read data from: \'{}\''.format(filename))
        print ('Script failed.')
        exit()
    worksheet_data = []
    for i, worksheet in enumerate(wb.sheets()):
        header_cells = worksheet.row(0)
        num_rows = worksheet.nrows - 1
        curr_row = 0
        header = [each.value for each in header_cells]
        while curr_row < num_rows:
            curr_row += 1
            row = [int(each.value) if isinstance(each.value, float)
                   else each.value
                   for each in worksheet.row(curr_row)]
            value_dict = dict(zip(header, row))
            worksheet_data.append(value_dict)
        else:
            DATA[worksheet.name] = worksheet_data
            worksheet_data = []


def valid_row(worksheet_name, row):
    WORKSHEET_NAME = worksheet_name
    REQUIRED_FIELDS = {
        'tasks'   : ['Task No','Target Device','Commands To Run'],
        'devices' : ['Device Name','IP Address','Username','Password'],
    }
    for field in REQUIRED_FIELDS[WORKSHEET_NAME]:
        if not DATA[WORKSHEET_NAME][row][field]:
            return False
    return True

def initalise_devices():
    WORKSHEET_NAME = 'devices'
    for row_no, row in enumerate(DATA[WORKSHEET_NAME]):
        if valid_row(WORKSHEET_NAME,row_no):
            device = Device()
            device.hostname     = str(DATA[WORKSHEET_NAME][row_no]['Device Name'].strip().lower())
            device.ipaddress    = str(DATA[WORKSHEET_NAME][row_no]['IP Address'].strip())
            device.username     = str(DATA[WORKSHEET_NAME][row_no]['Username'].strip())
            device.password     = str(DATA[WORKSHEET_NAME][row_no]['Password'].strip())
            device.enable_pass  = str(DATA[WORKSHEET_NAME][row_no]['Enable Password'].strip())
            device.platform     = str(DATA[WORKSHEET_NAME][row_no]['Cisco Platform (Default: No)'].strip().lower())
            if device.platform:
                if 'yes' in device.platform:
                    device.platform = 'cisco'
            d.devices[device.hostname] = device

def initalise_tasks():
    WORKSHEET_NAME = 'tasks'
    for row_no, row in enumerate(DATA[WORKSHEET_NAME]):
        if valid_row(WORKSHEET_NAME,row_no):
            task = Task()
            task.no          = int(DATA[WORKSHEET_NAME][row_no]['Task No'])
            task.enabled     = str(DATA[WORKSHEET_NAME][row_no]['Enabled (yes/no)'].strip().lower())
            task.description = str(DATA[WORKSHEET_NAME][row_no]['Task Description'])
            task.target      = str(DATA[WORKSHEET_NAME][row_no]['Target Device'].strip().lower())
            task.cmds        = str(DATA[WORKSHEET_NAME][row_no]['Commands To Run'].strip())
            task.delay       = str(DATA[WORKSHEET_NAME][row_no]['Task Delay (Default: 1)'])
            task.buffer      = str(DATA[WORKSHEET_NAME][row_no]['Buffer Size: (Default 5000 bytes)'])
            task.filename    = str(DATA[WORKSHEET_NAME][row_no]['Filename to store output'].strip())
            if task.target:
                task.target = task.target.splitlines()
            if task.cmds:
                task.cmds = task.cmds.splitlines()
            if task.delay:
                task.delay = float(task.delay)
            if task.buffer:
                task.buffer = int(task.buffer)
            if not task.delay:
                task.delay = float(1)
            if not task.buffer:
                task.buffer = int(10000)
            if not task.filename:
                task.filename = 'default_output.txt'
            if 'yes' in task.enabled:
                d.tasks[task.no] = task
#------------------------------------------
# Useful functions
#------------------------------------------
def get_device(device_name):
    return d.devices.get(device_name)

def get_task(task_no):
    return d.tasks.get(task_no)
#------------------------------------------
# Script Functions
#------------------------------------------
def run_command(session,task,device,command):
    if 'cisco' in device.platform:
        wait_for_cisco_prompt(session)
    print ("  ++ Command executed: {}".format(command))
    session.send("{}\n".format(command))
    time.sleep(task.delay)
    cmd_output = get_session_output(session,task.buffer)
    if 'cisco' in device.platform:
        while "#" not in cmd_output:
            print ("    ++ Output still being received")
            session.send("\n")
            cmd_output += get_session_output(session,task.buffer)
            time.sleep(0.2)
    return cmd_output

def get_session_output(session,bytes_received):
    output = session.recv(bytes_received).decode('UTF-8')
    return output

def wait_for_cisco_prompt(session):
    session.send("\n")
    time.sleep(0.3)
    prompt = get_session_output(session,1000)
    while "#" not in prompt:
        session.send("\n")
        time.sleep(0.3)
        prompt = get_session_output(session,1000)

def prepare_cisco_session(session, device):
    print ("++ Connection status: successful")
    print ("++ Cisco device mode set, preparing session")
    print ("  ++ Changing terminal length to 0")
    session.send("terminal length 0\n")
    print ("  ++ Checking enable mode status")
    session.send("\n")
    time.sleep(0.5)
    output = get_session_output(session,1000)
    if ">" in output:
        print ("    ++ Activating enable mode")
        session.send("enable\n")
        time.sleep(0.5)
        session.send(device.enable_pass+"\n")
        time.sleep(0.5)
        output = get_session_output(session,1000)
        if "#" in output:
            print ("    ++ Status: active\n")
        else:
            print ("    ++ Status: failed\n")
    elif "#" in output:
        print ("    ++ Status: active\n")
    else:
        print (" ++ Status: could not determine\n")

def enable_mode_active(session):
    session.send("\n")
    time.sleep(0.5)
    state = get_session_output(session,1000)
    if "#" in state:
        return True
    return False

def run_task(task_no):
    task = get_task(task_no)
    print ("\n===============================================")
    print ("Executing task no: {} ".format(task.no))
    print ("===============================================")
    if len(task.target) > 1:
        print ("++ Task will be executed on multiple devices")
    else:
        print ("++ Task will be executed on a single device")

    for device_name in task.target:
        device = get_device(device_name)
        print ("--------------------------------------------")
        print ("Connecting to {} on '{}':".format(device.hostname,device.ipaddress))
        print ("--------------------------------------------")
        #-------------------
        # Start SSH session
        #-------------------
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                device.ipaddress,
                username=device.username,
                password=device.password,
                allow_agent=False
            )
        except (
                paramiko.AuthenticationException,
                paramiko.SSHException,
                socket.error
        ) as e:
            print ('-- Aborting task')
            print ('  -- {}'.format(e))
            task.status[device.hostname] = 'Task failed : {}'.format(e)
            continue

        session = ssh.invoke_shell()

        if 'cisco' in device.platform:
            prepare_cisco_session(session,device)
            if not enable_mode_active(session):
                print ("-- Aborting task, could not enter enable mode")
                print ("  -- Recommendation 1: check enable password")
                print ("  -- Recommendation 2: disable Cisco platform if this is not a Cisco device")
                task.status[device.hostname] = 'Task failed, could not enter enable mode'
                return

        print ("++ The following commands will be run:")
        task.devices[device.hostname] = Output()
        for cmd in task.cmds:
            cmd_output = run_command(session,task,device,cmd)
            task.devices[device.hostname].cmd_output[cmd] = cmd_output.splitlines()
        else:
            print ("  ++ Output written to: {}".format(task.filename))
            task.status[device.hostname] = 'Task executed succesfully'
            write_task_output_to_file(task)

def run_all_task():
    for task in sorted(d.tasks):
        run_task(task)
# ------------------------------------------------------------
# Write the output that was captured for each task to a file
# -------------------------------------------------------------
def write_task_output_to_file(task):
    with open(task.filename,"w") as output_file:
        capture_time = time.asctime( time.localtime(time.time()))
        for device in task.devices:
            print ("*******************************************************",file=output_file)
            print ("++ Output captured from: '{}' @ {}:".format(device,capture_time),file=output_file)
            print ("*******************************************************",file=output_file)
            for cmd in task.devices[device].cmd_output:
                print ("----------------------------------------------------------",file=output_file)
                print ("Output for command: '{}'".format(cmd),     file=output_file)
                print ("----------------------------------------------------------",file=output_file)
                for line in task.devices[device].cmd_output[cmd]:
                    print (line, file=output_file)

def write_task_summary_to_file():
    with open("task_summary.txt","w") as output_file:
        capture_time = time.asctime( time.localtime(time.time()))
        print ("=================================",file=output_file)
        print ("Task Execution Summary @ {}: ".format(capture_time),file=output_file)
        print ("=================================",file=output_file)
        for task_no in d.tasks:
            task = get_task(task_no)
            print ('-- Task No: {}'.format(task.no),file=output_file)
            for device in sorted(task.status):
                print ('  -- \'{}\': {}'.format(device,task.status[device]),file=output_file)
        print ("\n\n****************************************")
        print (" task_summary.txt file has been generated")
        print ("****************************************")


def main(argv):
    arg_length = len(sys.argv)
    print ('+-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-+')
    print ('    SSH Automator v{}'.format(__version__))
    print ('+-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-+')
    if arg_length < 2:
        print ('Usage: python {} <spreadsheet.xlsx>' .format(sys.argv[0]))
        exit()
    if sys.argv[1]:
        filename = sys.argv[1]
    try:
        read_database_from_file(filename)
        print ('Data read from: \'{}\''.format(filename))
        initalise_devices()
        initalise_tasks()
        run_all_task()
        write_task_summary_to_file()
    except IOError:
        exit()

# Run the script
if __name__ == '__main__':
    d = Database()
    main(sys.argv)
