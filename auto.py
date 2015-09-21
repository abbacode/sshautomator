__version__ = 3.0
__author__ = 'Abdul El-Assaad'

from auto_data import Database
import argparse

def setup_parser():
    """
    Define all the CLI arguments here
    """
    parser = argparse.ArgumentParser(description='SSH Task Automation Tool v{}'.format(__version__))

    parser.add_argument('-file',default='auto.xls', dest='filename', required=True,
                        help='Specify the name of the file which contains the tasks')

    parser.add_argument('-turbo', action='store_true', dest='turbo', default=False,
                        help='Enable multiprocessing mode, task executed in random order')

    results = parser.parse_args()
    return results

if __name__ == '__main__':

    args = setup_parser()
    db = Database(args.filename)

    if args.turbo:
        db.start_all_tasks_turbo()
    else:
        db.start_all_tasks_normal()
