from multiprocessing import Process
import multiprocessing as mp


class Database(object):
    def __init__(self, filename):
        self.raw_data = {}
        self.devices = {}
        self.tasks = {}

        self.read_database_from_file(filename)
        self.initalise_devices()
        self.initalise_tasks()

    def read_database_from_file(self,filename):
        """
        Read data from the workbook and load all rows in raw_data dictionary
        """
        import xlrd

        try:
            workbook = xlrd.open_workbook(filename)
        except IOError as error:
            print (error)
            exit()

        worksheet_data = []
        for i, worksheet in enumerate(workbook.sheets()):
            header_cells = worksheet.row(0)
            num_rows = worksheet.nrows - 1
            current_row = 0
            header = [each.value for each in header_cells]
            while current_row < num_rows:
                current_row += 1
                row = [float(each.value) if isinstance(each.value, float) else each.value
                       for each in worksheet.row(current_row)]
                value_dict = dict(zip(header, row))
                worksheet_data.append(value_dict)
            else:
                self.raw_data[worksheet.name] = worksheet_data
                worksheet_data = []

    def valid_row(self,worksheet_name, row):
        """
        Used to validate whether a row has the mandatory fields.
        If a cell is empty then the task is not considered valid.
        """
        required_fields = {
            'tasks': ['Task No','Target Device','Commands To Run'],
            'devices': ['Device Name','IP Address','Username','Password'],
        }
        missing_field=[False for f in required_fields[worksheet_name] if not self.raw_data[worksheet_name][row][f]]

        if not missing_field:
            return True


    #-----------------------------------------
    # Initalise all the valid devices
    #------------------------------------------
    def initalise_devices(self):
        """
        Parse over the raw_data dictionary and read the info from the devices worksheet.
        Check each row to make sure it has mandatory cells.
        """
        worksheet_name = 'devices'
        for row_no, row in enumerate(self.raw_data[worksheet_name]):
            if self.valid_row(worksheet_name,row_no):
                device = Device()
                device.hostname = str(self.raw_data[worksheet_name][row_no]['Device Name'].strip().lower())
                device.ctype = str(self.raw_data[worksheet_name][row_no]['Telnet or SSH'].strip().lower())
                device.ipaddress = str(self.raw_data[worksheet_name][row_no]['IP Address'].strip())
                device.username = str(self.raw_data[worksheet_name][row_no]['Username'].strip())
                device.password = str(self.raw_data[worksheet_name][row_no]['Password'].strip())
                device.enable_pass = str(self.raw_data[worksheet_name][row_no]['Enable Password'].strip())
                device.platform = str(self.raw_data[worksheet_name][row_no]['Cisco Platform (Default: No)'].strip().lower())

                if not device.ctype:
                    device.ctype = 'ssh'
                if 'yes' in device.platform:
                    device.platform = 'cisco'
                else:
                    device.platform = 'other'
                self.devices[device.hostname] = device

    def initalise_tasks(self):
        """
        Parse over the raw_data dictionary and read the info from the tasks worksheet.
        Check each row to make sure it has mandatory cells.
        """
        from decimal import Decimal
        worksheet_name = 'tasks'
        for row_no, row in enumerate(self.raw_data[worksheet_name]):
            if self.valid_row(worksheet_name,row_no):
                # read the data for each task
                task = Task()
                task.no = int(self.raw_data[worksheet_name][row_no]['Task No'])
                task.enabled = str(self.raw_data[worksheet_name][row_no]['Enabled (yes/no)'].strip().lower())
                task.description = str(self.raw_data[worksheet_name][row_no]['Task Description'])
                task.target = str(self.raw_data[worksheet_name][row_no]['Target Device'].strip().lower())
                task.cmds = str(self.raw_data[worksheet_name][row_no]['Commands To Run'].strip())
                task.delay = str(self.raw_data[worksheet_name][row_no]['Task Delay (Default: 0.5)'])
                task.buffer = str(self.raw_data[worksheet_name][row_no]['Buffer Size: (Default 65000 bytes)'])
                task.filename = str(self.raw_data[worksheet_name][row_no]['Filename to store output'].strip())

                # format the output
                if task.target:
                    task.target = task.target.splitlines()
                    for device in task.target:
                        task.devices[device] = TaskOutput()
                        if device not in self.devices:
                            print ('Task ({}) will not be executed [no device].'.format(task.no,device))
                            task.enabled = 'no'
                if task.cmds:
                    task.cmds = task.cmds.splitlines()
                if task.delay:
                    task.delay = float(Decimal(task.delay))
                if task.buffer:
                    task.buffer = float(Decimal(task.buffer))
                if not task.delay:
                    task.delay = float(1)
                if not task.buffer:
                    task.buffer = int(65000)
                if not task.filename:
                    task.filename = 'default_output.txt'
                if 'yes' in task.enabled:
                    self.tasks[task.no] = task

    #----------------------------
    # Generic task functions
    #----------------------------
    def get_device(self,device_name):
        return self.devices.get(device_name)

    def get_task(self,task_no):
        return self.tasks.get(task_no)

    def divide_tasks_into_chunks(self,lst,n):
        """
        Will break up a list into 'n' segments
        """
        return [ lst[i::n] for i in range(n) ]

    #----------------------------
    # Save tasks output functions
    #----------------------------
    def write_task_output(self,task):
        """
        Save the task output to a file.
        """
        with open(task.filename,"w") as output_file:
            capture_time = task.time_executed
            for device in task.devices:
                print ("*******************************************************",        file=output_file)
                print ("++ Output captured from: '{}' @ {}:".format(device,capture_time),file=output_file)
                print ("*******************************************************",        file=output_file)
                for cmd in task.devices[device].cmd_output:
                    print ("----------------------------------------------------------", file=output_file)
                    print ("Output for command: '{}'".format(cmd),                       file=output_file)
                    print ("----------------------------------------------------------", file=output_file)
                    for line in task.devices[device].cmd_output[cmd]:
                        print (line, file=output_file)

    def write_task_summary_header(self):
        """
        The task summary will provide a high level snapshot for every task that
        was executed and whether it was successful or not.
        """
        import time
        with open("task_summary.txt","w") as output_file:
            capture_time = time.asctime( time.localtime(time.time()))
            print ("==================================================",                     file=output_file)
            print ("Task Execution Summary @ {}:                      ".format(capture_time),file=output_file)
            print ("==================================================",                     file=output_file)
            print (self.show_table_header,file=output_file)

    #----------------------------
    # Show tasks output functions
    #----------------------------
    @property
    def show_table_header(self):
        header = ''
        header+=('+------+---------------+------------------+---------------------------------+\n')
        header+=('| Task |  Device       | IP Address       | Task Status                     |\n')
        header+=('+------+---------------+------------------+---------------------------------+')
        return header

    def show_task_status(self,device,task,session):
        """
        Display the task and whether it was executed successfully
        """
        print("| {:<4} | {:<13} | {:<16} | {:<31} |".format(task.no,
                                                            device.hostname,
                                                            device.ipaddress,
                                                            task.status[device.hostname]))

        # Have to save this output here, otherwise turbo/multiprocess mode garbles it up for some reason...
        with open("task_summary.txt","a") as output_file:
            print("| {:<4} | {:<13} | {:<16} | {:<31} |".format(task.no,
                                                                device.hostname,
                                                                device.ipaddress,
                                                                task.status[device.hostname]), file=output_file)

    def execute_task_cmds(self,device,task,session):
        """
        Cycle through the commands for this task and execute them one at a time
        """
        import time
        session.delay = task.delay
        session.buffer = task.buffer

        task.time_executed = time.asctime( time.localtime(time.time()))
        for cmd in task.cmds:
            task.devices[device.hostname].cmd_output[cmd] = session.command(cmd).splitlines()
        else:
            task.status[device.hostname] = 'Task completed'
            self.write_task_output(task)


    def update_task_status(self,device,task,session,status=''):
        """
        Update the status for the task.

        If no input is entered it will default to the session error message.
        """
        if status:
            session.error_msg = status
        task.status[device.hostname]='{}'.format(session.error_msg)
        self.show_task_status(device,task,session)

    def start_all_tasks_normal(self):
        """
        Start all the task using single processing mode.

        A single process will be spun up and all task will be executed
        sequentially.
        """
        self.write_task_summary_header()

        print ('Starting Task Automation Tool in STANDARD mode... ')
        print(self.show_table_header)
        for task in self.tasks:
            task_no = [task]
            self.run_task(task_no,None)
        print ('\nTask execution completed (check task_summary.txt).')

    def start_all_tasks_turbo(self):
        """
        Start all the task using multiprocessing mode.

        A process will be spun for each CPU and tasks will be distributed
        across all processes.  Task will be executed in parallel and not in sequence.
        """
        print ('Starting Task Automation Tool in TURBO mode... ')
        output = mp.Queue()
        cpu_count = mp.cpu_count()
        tasks=[task for task in self.tasks]
        chunks=self.divide_tasks_into_chunks(tasks,cpu_count)
        processes = []
        for i in range(cpu_count):
            process_name = 'worker {}'.format(i)
            if chunks[i]:
                print ('-- starting {} to run task: {}'.format(process_name,chunks[i]))
                processes.append(mp.Process(name=process_name,
                                            target=self.run_task,
                                            args=(chunks[i],output)))
        self.write_task_summary_header()

        print(self.show_table_header)
        for p in processes:
            p.start()
        for p in processes:
            p.join()
        print ('\nTask execution completed (check task_summary.txt).')

    def setup_task_session(self,device):
        """
        Establish a session to the relevant device.
        If SSH or Telnet is not defined a default Unknown session is used
        for error handling purposes.  This will generate a notification in
        the task execution screen.
        """
        from auto_session import SSH
        from auto_session import Telnet
        from auto_session import Unknown

        if 'ssh' in device.ctype:
            session = SSH(device.ipaddress,device.username,device.password)
        elif 'telnet' in device.ctype:
            session = Telnet(device.ipaddress,device.username,device.password)
        else:
            session = Unknown()
        session.connect()
        return session

    def run_task(self,task_data,output):
        """
        Run the actual task or task depending on whether single or multiprocess mode was used.
        """
        for t in task_data:
            task = self.get_task(t)

            for device_name in task.target:
                device=self.get_device(device_name)
                session=self.setup_task_session(device)

                if not session.established:
                    self.update_task_status(device,task,session)
                    continue

                if device.is_cisco:
                    session.prepare_cisco_session(device)
                    if not session.enable_mode:
                        self.update_task_status(device,task,session,'Error: No Enable Mode')
                        continue
                self.execute_task_cmds(device,task,session)
                self.show_task_status(device,task,session)
                session.close()

class Device(object):
    def __init__(self):
        self.hostname = ''                  # Device hostname
        self.ipaddress = ''                 # Device ip address
        self.username = ''                  # Device username to login
        self.password = ''                  # Device password to login
        self.enable_pass = ''               # Device enable password (if cisco)
        self.ctype = ''                     # Connection type (SSH or Telnet)
        self.platform = 'cisco'             # Is this a cisco device

    @property
    def is_cisco(self):
        if 'cisco' in self.platform:
            return True

class Task(object):
    def __init__(self):
        self.no = -1                        # Task number
        self.description = ''               # Task description
        self.enabled = False                # Is the task enabled?
        self.target = {}                    # Target devices
        self.cmds = []                      # Commands that will be executed
        self.delay = 0                      # Delay before recieving output (non-cisco devices)
        self.buffer = 0                     # Buffer size to recieve for each packet
        self.filename = ''                  # Filename that the output will be saved to
        self.status = {}                    # Stores whether the task was executed successfully or not
        self.devices = {}                   # Stores the output of each command
        self.time_executed = 0              # Timestamp for when the task was executed

class TaskOutput(object):
    def __init__(self):
        from collections import OrderedDict
        self.cmd_output = OrderedDict()
