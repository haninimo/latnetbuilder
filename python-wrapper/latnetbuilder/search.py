import subprocess
import time
import logging
import traceback
from IPython.display import display
import numpy as np

from .parse_output import parse_output, Result
from .gui.output import output, create_output
from .gui.progress_bars import progress_bars

logging.basicConfig(filename='stderr.txt')

class Search():
    def __init__(self):
        self.modulus = ''
        self.dimension = 0
        self.multilevel_filters = []
        self.combiner = ''
        self.exploration_method = ''
        self.figure_of_merit = ''
        self.figure_power = '2'
        self.weights = []
        self.weights_power = 2  # to be changed for inf norm ?
        self.filters = []
        self.output = None

    def construct_command_line(self):
        pass
    def search_type(self):
        pass

    def _launch_subprocess(self, stdout_file, stderr_file):
        '''Call the C++ process using the Python module subprocess.
        
        This function is used by the GUI, but should NOT be called directly by the end user.'''

        command = self.construct_command_line()
        process = subprocess.Popen(['exec ' + ' '.join(command)], stdout=stdout_file, stderr=stderr_file, shell=True)
        # The exec keyword is essential as it allows to kill the latnetbuilder process using process.kill()
        # This syntax may not work without the exec keyword.
        return process

    def _parse_progress(self, line):
        '''Parse the progress information delivered by the C++ stdout. Useful for progress bars.'''
        try_split = line.split('-')
        if len(try_split) == 1:
            current_nb_nets = int(line.split('/')[0].split(' ')[-1])
            total_nb_nets = int(line.split('/')[1])
            return (0, float(current_nb_nets) / total_nb_nets)
        elif len(try_split) == 2:
            current_nb_nets = int(try_split[1].split('/')[0].split(' ')[-1])
            total_nb_nets = int(try_split[1].split('/')[1])
            current_dim = int(try_split[0].split('/')[0].split(' ')[-1])
            total_dim = int(try_split[0].split('/')[1])
            return (float(current_dim) / total_dim, float(current_nb_nets) / total_nb_nets)

    def execute(self, stdout_filename='cpp_outfile.txt', stderr_filename='cpp_errfile.txt', delete_files=True, display_progress_bar=False):
        '''Call the C++ process and monitor it.

        Arguments (all optional):
            + stdout_filename: name of the file which will contain the std output of the C++ executable
            + stdout_filename: name of the file which will contain the error output of the C++ executable
            + delete_files: if set to True, the log files are deleted at the end of the process
            + display_progress_bars: if set to True, ipywidgets progress bars are displayed (should be used only in the notebook)
        
        This function should be used by the end user if he instanciates a Search object.'''

        stdout_file = open(stdout_filename, 'w')
        stderr_file = open(stderr_filename, 'w')
        process = self._launch_subprocess(stdout_file, stderr_file)
        self._monitor_process(process, stdout_filename=stdout_filename, stderr_filename=stderr_filename, display_progress_bar=display_progress_bar)

    def _monitor_process(self, process, stdout_filename, stderr_filename, gui=None, display_progress_bar=False, in_thread=False):
        '''Monitor the C++ process.
        
        This function is called inside a thread by the GUI (with in_thread=True, and gui contains the gui object).
        It is called outside of any thread by the execute method (with in_thread=False).
        
        The function deals the monitoring both with and without a GUI interface. Thus it is a bit lenghty
        because the same information has to be treated in two different ways.'''

        search_type = self.search_type()
        try:
            if gui is not None:
                abort = gui.button_box.abort
                my_progress_bars = gui.progress_bars
                display_progress_bar = True
                my_result_obj = gui.output.result_obj
            else:
                if display_progress_bar:
                    # create and display the progress bars
                    my_progress_bars = progress_bars()
                    my_progress_bars.progress_bar_dim.layout.display = 'flex'
                    my_progress_bars.progress_bar_nets.layout.display = 'flex'
                    display(my_progress_bars.progress_bar_nets)
                    display(my_progress_bars.progress_bar_dim)
                self.output = output()
                my_result_obj = self.output.result_obj
            
            while process.poll() is None:   # while the process is not finished
                time.sleep(1)
                with open('cpp_outfile.txt','r') as f:
                    data = f.read()
                try:
                    last_line = data.split('\n')[-2]    # read the before last line (the last line is always blank)
                    prog_dimension, prog_net = self._parse_progress(last_line)
                    if display_progress_bar:    # update progress bars
                        my_progress_bars.progress_bar_nets.value = prog_net
                        my_progress_bars.progress_bar_dim.value = prog_dimension
                except:
                    pass 
            
            if display_progress_bar:
                my_progress_bars.progress_bar_dim.layout.display = 'none'
                my_progress_bars.progress_bar_nets.layout.display = 'none'
            if gui is not None:
                abort.button_style = ''
                abort.disabled = True

            if process.poll() == 0:     # the C++ process has finished normally
                with open(stdout_filename) as f:
                    console_output = f.read()
                try:
                    with open('output_latnet.txt') as f:
                        file_output = f.read()
                except:
                    file_output = None
                parse_output(console_output, file_output, my_result_obj, search_type)

                if gui is not None:
                    gui.output.result_html.value = "<span> <b> Lattice Size </b>: %s </span> \
                    <p> <b> Generating Vector </b>: %s </p>\
                    <p> <b> Merit value </b>: %s </p>\
                    <p> <b> CPU Time </b>: %s s </p>" % (str(my_result_obj.latnetbuilder.size), str(my_result_obj.latnetbuilder.gen), str(my_result_obj.merit), str(my_result_obj.seconds))
                    create_output(gui.output, in_thread=in_thread)
                else:
                    print("Result:\nLattice Size: %s \nGenerating Vector: %s \nMerit value: %s \nCPU Time: %s s" 
                    % (str(my_result_obj.latnetbuilder.size), str(my_result_obj.latnetbuilder.gen), str(my_result_obj.merit), str(my_result_obj.seconds)))

            else:   # an error occured in the C++ process
                with open(stderr_filename) as f:
                    err_output = f.read()
                
                if gui is not None:
                    gui.output.result_html.value = '<span style="color:red"> %s </span>' % (err_output)
                    if err_output == '':    # no error message
                        if abort.value == True:
                            gui.output.result_html.value = 'You aborted the search.'
                        else:
                            gui.output.result_html.value = '<span style="color:red"> The C++ process crashed without returning an error message. </span>'
                
                else:
                    if err_output == '':
                        print("The C++ process crashed without returning an error message.")
                    else:
                        print(err_output)

            
        except Exception as e:
            logging.warn(e)
            logging.warn(traceback.format_exc())
            if gui is not None:
                gui.output.result_html.value += '<span style="color:red"> An error happened in the communication with the C++ process. </span>'
            else:
                print("An error happened in the communication with the C++ process.")

    def rich_output(self):
        '''Print a rich output (plot and code) for the Search result'''
        if self.output is None:
            print("Run self.execute() before outputing")
        else:
            display(self.output.output)
            create_output(self.output)

    def points(self, verbose=0):
        '''Compute and return the QMC points of the Search result.
        
        The points are returned as a 2-dimensional numpy array, the first index corresponds to the index of the point,
        and the second corresponds to the coordinate.
        
        If verbose is >0, the Python code executed is printed.'''

        if self.output is None:
            print("Run self.execute() before using points")
        else:
            if len(self.output.output.children) == 0:
                create_output(self.output, create_graph=False)
            
            code = self.output.output.children[2].value
            if verbose > 0:
                print('Executing....')
                print(code)

            glob = {}
            exec(code, glob)    # execute string as Python code. Potentially dangerous if the .txt files in code_output 
                                # have been tampered with.
            return np.array(glob['points'])


class SearchLattice(Search):
    '''Specialization of the Search class to search for lattices'''

    def __init__(self):
        self.lattice_type = ''
        self.embedded_lattice = False
        super(SearchLattice, self).__init__()   # calls the constructor of the parent class Search

    def __repr__(self):
        return "TODO"
          
        
    def construct_command_line(self):
        '''Construct and return the command line to call LatNetBuilder as a list of strings'''

        from . import LATBUILDER
        command = [LATBUILDER,
                   '--set-type', 'lattice',
                   '--construction', self.lattice_type,
                   '--multilevel', str(self.embedded_lattice).lower(),
                   '--modulus', self.modulus,
                   '--figure-of-merit', self.figure_of_merit,
                   '--norm-type', self.figure_power,
                   '--construction', self.exploration_method,
                   '--weights-power', str(self.weights_power),
                   '--verbose', '1',
                   '--dimension', str(self.dimension),
                   ]
        command += ['--weights'] + self.weights
        if self.filters != []:
            command += ['--filters'] + self.filters
        if self.multilevel_filters != []:
            command += ['--multilevel-filters'] + self.multilevel_filters
        if self.combiner != '':
            command += ['--combiner', self.combiner]
        if self.lattice_type == 'polynomial':
            command += ['--output-format', 'file:output_latnet.txt,format:gui']
        return command

    def search_type(self):
        command = self.construct_command_line()
        if 'ordinary' in command:
            return 'ordinary'
        elif 'polynomial' in command:
            return 'polynomial'


class SearchNet(Search):
    '''Specialization of the Search class to search for nets'''

    def __init__(self):
        self.set_type = 'net'
        self.construction = ''
        super(SearchNet, self).__init__()       # calls the constructor of the parent class Search
    
    def construct_command_line(self):
        '''Construct and return the command line to call LatNetBuilder as a list of strings'''

        from . import LATBUILDER
        command = [LATBUILDER,
                   '--set-type', 'net',
                   '--construction', self.construction,
                   '--set-type', self.set_type,
                   '--size', self.modulus,
                   '--exploration-method', self.exploration_method,
                   '--dimension', str(self.dimension),
                   '--verbose', '2',
                   '--output-format', 'file:output_latnet.txt,format:gui'
                   ]

        if len(self.filters) > 0:
            command += ['-add-figure', self.filters[-1]]
        
        command.append('--add-figure')
        command.append('/'.join([self.figure_of_merit, '1', self.figure_power, ' '.join(self.weights), str(self.weights_power)]))

        if self.combiner != '':
            command += ['--combiner', self.combiner]
        return command

    def search_type(self):
        return 'digital-' + self.construction