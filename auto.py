__author__ = 'Abdul Karim El-Assaad'
__version__ = 1.5

import xlrd
import paramiko
import time
import socket
import re

class Automate(object):
    def __init__(self):
        self.database = {}      # Raw information read from auto.xls
        self.tasks = {}         # Valid task extract from database
        self.device_info = {}   # Information obtained from devices worksheet
        self.output = {}        # Output/result of the tasks that are executed
        self.summary = {}       # Summary of whether the task were successful or not

        self.ReadTaskFromFile()
        self.GetDevicesFromDatabase()
        self.GetTasksFromDatabase()
        self.RunAllTask()
        self.WriteTaskSummaryToFile()

    #----------------------------------------------------------------
    # Read information from the auto.xlsx
    # Information will be stored by worksheet name, row, column name
    #-----------------------------------------------------------------
    def ReadTaskFromFile(self):
        try:
            wb = xlrd.open_workbook('auto.xls')
        except:
            print ("Cannot open auto.xls file, aborting script")
            exit()

        temp_db = []
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
                temp_db.append(value_dict)
            else:
                self.database[worksheet.name] = temp_db
                temp_db = [] 

    # -----------------------------------------------------------------------------------------
    # Read info from database dictionary, specifically device info such as username/passwords
    # -----------------------------------------------------------------------------------------
    def GetDevicesFromDatabase(self):
        for device in self.database["Devices"]:
            if self.ValidDeviceInDB(device):
                device_name = str(device["Name"]).strip()
                if device_name not in self.device_info:
                    tempObj = DeviceTemplate()
                    tempObj.name = str(device["Name"]).strip()
                    tempObj.ip_address = str(device["IP Address"]).strip()
                    tempObj.username = str(device["Username"]).strip()
                    tempObj.password = str(device["Password"]).strip()
                    tempObj.enable = str(device["Enable Password"]).strip()
                    tempObj.cisco_platform = str(device["Cisco Platform (Default: No)"]).strip().upper()
                    # Create a new device entry
                    self.device_info[device_name] = tempObj

    def FindExactString(self,word):
        return re.compile(r'^\b({0})$\b'.format(word),flags=re.IGNORECASE).search

    def GetDevice(self,device_name):
        for device in self.device_info:
            if self.FindExactString(device_name)(device):
                return self.device_info[device]
        return None

    #--------------------------------------------------------
    # Read over the raw database and grab all the valid tasks
    #--------------------------------------------------------
    def GetTasksFromDatabase(self):
        for task in self.database['Tasks']:
            task_no = task["Task No"]
            if self.ValidTaskInDB(task):
                valid_devices = self.TaskHasValidDevices(task)
                if valid_devices:
                    if task_no not in self.tasks:
                        tempObj = TaskTemplate()
                        tempObj.no          = task["Task No"]
                        tempObj.description = task["Task Description"]
                        tempObj.target      = task["Target Device"].splitlines()
                        tempObj.cmds        = task["Commands To Run"].splitlines()
                        tempObj.delay       = task["Task Delay (Default: 1)"]
                        tempObj.buffer      = task["Buffer Size: (Default 5000 bytes)"]
                        tempObj.filename    = task["Filename to store output"]
                        if not tempObj.delay:
                            tempObj.delay = 1
                        if not tempObj.buffer:
                            tempObj.buffer = 5000
                        self.tasks[task_no] = tempObj
                else:
                    self.summary[task_no] = "Task not executed: incomplete device details in spreadsheet"
            else:
                if task_no and not self.summary.get(task_no):
                    self.summary[task_no] = "Task not executed: incomplete task entry in spreadsheet"

    def GetTask(self,task_no):
        for task in self.tasks:
            if task_no == task:
                return self.tasks[task]
        return None
    # ------------------------------------------------------------------------------------------
    # Capture the output of each task in the task dictionary so it can be shown at future state
    # ------------------------------------------------------------------------------------------
    def CaptureTaskOutput(self,task_no,device_name,cmd_run,output_captured):
        if task_no not in self.output:
            self.output[task_no] = {}
            self.output[task_no]["Device"] = []
            self.output[task_no]["Commands"] = []
            self.output[task_no]["Output"] = []
        self.output[task_no]["Device"].append(device_name)
        self.output[task_no]["Commands"].append(cmd_run)
        self.output[task_no]["Output"].append(output_captured)

    #----------------------------------------------------------------
    # Grab the session output and convert it to readable text format
    #----------------------------------------------------------------
    def GetSessionOutput(self,session,bytes_received):
        output = session.recv(bytes_received)
        output = output.decode('UTF-8')
        return output
    # -----------------------------------------------
    # Function to send a command to a device via SSH
    # -----------------------------------------------
    def RunCommand(self,session,command,buffer_size=1000,sleep_time=2,cisco_device=False):
        if cisco_device:
            self.WaitForCiscoPrompt(session)

        print ("  ++ Command executed: {}".format(command))
        session.send("{}\n".format(command))
        time.sleep(sleep_time)
        output = self.GetSessionOutput(session,buffer_size)

        if cisco_device:
            while "#" not in output:
                print ("    ++ Output still being received")
                session.send("\n")
                output += self.GetSessionOutput(session,buffer_size)
                time.sleep(0.5)
        return (output)

    # -----------------------------------------------------------------
    # Function to prepare the SSH session, applicable to Cisco devices
    # -----------------------------------------------------------------
    def PrepareCiscoSession(self,session,enable_password):
        print ("++ Connection status: successful")
        print ("++ Cisco device mode set, preparing session")
        print ("  ++ Changing terminal length to 0")
        session.send("terminal length 0\n")
        print ("  ++ Checking enable mode status")
        session.send("\n")
        time.sleep(0.8)
        output = self.GetSessionOutput(session,1000)
        if ">" in output:
            print ("    ++ Activating enable mode")
            session.send("enable\n")
            time.sleep(0.8)
            session.send(enable_password+"\n")
            time.sleep(0.8)
            output = self.GetSessionOutput(session,1000)
            if "#" in output:
                print ("    ++ Status: active\n")
            else:
                print ("    ++ Status: failed\n")
        elif "#" in output:
            print ("    ++ Status: active\n")
        else:
            print (" ++ Status: could not determine\n")

    def WaitForCiscoPrompt(self,session):
        session.send("\n")
        time.sleep(0.5)
        prompt = self.GetSessionOutput(session,1000)
        while "#" not in prompt:
            session.send("\n")
            time.sleep(0.5)
            prompt = self.GetSessionOutput(session,1000)

    def EnableModeActive(self,session):
        session.send("\n")
        time.sleep(0.5)
        state = self.GetSessionOutput(session,1000)
        if "#" in state:
            return True
        return False

    # -------------------------------------------------------------
    # Function to execute the specified task based on task number
    # -------------------------------------------------------------
    def RunTask(self,task_no):
        task = self.GetTask(task_no)

        print ("\n===============================================")
        print ("Executing task no: {} ".format(task_no))
        print ("===============================================")

        if len(task.target) > 1:
            print ("++ Task will be executed on multiple devices")
        else:
            print ("++ Task will be executed on a single device")

        for device_name in task.target:
            device = self.GetDevice(device_name)
            print ("--------------------------------------------")
            print ("Connecting to {} on '{}':".format(device.name,device.ip_address))
            print ("--------------------------------------------")
            #-------------------
            # Start SSH session
            #-------------------
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(device.ip_address, username=device.username, password=device.password, allow_agent=False)
            except paramiko.AuthenticationException as e:
                print ("-- Task aborted: {}".format(e))
                self.summary[task_no] = "Task not executed: {}".format(e)
                return
            except paramiko.SSHException as e:
                print ("-- Task aborted: {}".format(e))
                self.summary[task_no] = "Task not executed: {}".format(e)
                return
            except socket.error as e:
                print ("-- Task aborted: {}".format(e))
                self.summary[task_no] = "Task not executed: {}".format(e)
                return
            target = ssh.invoke_shell()

            if device.cisco_platform == "YES":
                self.PrepareCiscoSession(target,device.enable)
                if not self.EnableModeActive(target):
                    print ("-- Aborting task, could not enter enable mode")
                    print ("  -- Recommendation 1: check enable password")
                    print ("  -- Recommendation 2: disable Cisco platform if this is not a Cisco device")
                    self.summary[task_no] = "Task not executed, could not enter enable mode"
                    return

            print ("++ The following commands will be run:")
            for cmd in task.cmds:
                if device.cisco_platform == "YES":
                    output = self.RunCommand(target,cmd,task.buffer,task.delay,True)
                else:
                    output = self.RunCommand(target,cmd,task.buffer,task.delay,False)
                self.CaptureTaskOutput(task_no,device.name,cmd,output)
                self.WriteTaskOutputToFile(task_no)
            else:                
                print ("  ++ Output written to: {}".format(task.filename))
                self.summary[task_no] = "Task executed"
                

    # ------------------------------------
    # Function to execute all valid task
    # ------------------------------------
    def RunAllTask(self):
        for task in sorted(self.tasks):
            self.RunTask(task)

    # ------------------------------------------------------------
    # Write the output that was captured for each task to a file
    # -------------------------------------------------------------
    def WriteTaskOutputToFile(self,task_no):
        task = self.GetTask(task_no)
        filename = task.filename
        with open(filename,"w") as output_file:
            last_device_name = "_blank_"
            
            for no, cmd in enumerate(self.output[task_no]["Commands"]):
                current_device_name = self.output[task_no]["Device"][no]
                if last_device_name != current_device_name:
                    last_device_name = current_device_name
                    print ("",file=output_file)
                    capture_time = time.asctime( time.localtime(time.time()))
                    print ("*******************************************************",file=output_file)
                    print ("++ Output captured from: '{}' @ {}:".format(current_device_name,capture_time),file=output_file)
                    print ("*******************************************************",file=output_file)
                print ("----------------------------------------------------------",file=output_file)
                print ("Output for command: '{}'".format(cmd),     file=output_file)
                print ("----------------------------------------------------------",file=output_file)
                command_output_as_list = self.output[task_no]["Output"][no].splitlines()
                for each_line in command_output_as_list:
                    print (each_line, file=output_file)

    def WriteTaskSummaryToFile(self):
        with open("task_summary.log","w") as output_file:
            print ("=================================",file=output_file)
            print ("Task Execution Summary: ",file=output_file)
            print ("=================================",file=output_file)
            for task_no in self.summary:
                print ("-- Task No: '{}' status: {}".format(task_no,self.summary[task_no]),file=output_file)
        print ("\n\n****************************************")
        print (" task_summary.log file has been generated")
        print ("****************************************")

    def ValidDeviceInDB(self,device_entry):
        if device_entry["Name"]         and \
           device_entry["IP Address"]   and \
           device_entry["Username"]     and \
           device_entry["Password"]: return True
        return False

    def ValidTaskInDB(self,task):
        if task["Task No"]                  and \
           task["Target Device"]            and \
           task["Commands To Run"]          and \
           task["Filename to store output"]: return True
        return False

    def TaskHasValidDevices(self,task):
        for device in task["Target Device"].splitlines():
            if not self.GetDevice(device):
                return False
        return True


class DeviceTemplate(object):
    def __init__(self):
        self.name = "TBD"
        self.ip_address = "TBD"
        self.username = "TBD"
        self.password = "TBD"
        self.enable = "TBD"
        self.cisco_platform = "TBD"

class TaskTemplate(object):
    def __init__(self):
        self.no = "TBD"
        self.description = "TBD"
        self.target = []
        self.cmds = []
        self.delay = "TBD"
        self.buffer = "TBD"
        self.filename = "TBD"

# Run the script
if __name__ == '__main__':
    auto = Automate()
    
