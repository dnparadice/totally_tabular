import pandas
import abc
import matplotlib.pyplot as py_plot
import tkinter
from tkinter import filedialog
from pathlib import Path
import pint
import sys
import skrf

"""  -----------------------------------  Module context items ----------------------------------------------------  """

totally_tabular_logging_flag = True
totally_tabular_logging_method = print



def log(text_in: str):

    """ a method for logging info in the tabular library and a really good reason to not use import * when importing
    this library """
    if totally_tabular_logging_flag is True:
        # you can attach your own logger by setting the module level variable to your preferred logging method
        totally_tabular_logging_method(text_in)


"""  ------------------------------------ Dataset Types - Extends Pandas Data Frames -----------------------------   """


# class SubclassedSeries(pandas.Series):
#     @property
#     def _constructor(self):
#         return SubclassedSeries
#
#     @property
#     def _constructor_expanddim(self):
#         return S2PDataFrame
#
#
# class S2PDataFrame(pandas.DataFrame):
#     """ subclassing data frames is not awesome because you cant use the built in viewer also as I understand it
#     some built in methods just make new dataframe objects and you loose any attributes you set in this class ...
#     also dataframes dont support metadata ... why is pandas so popular???"""
#     @property
#     def _constructor(self):
#         return S2PDataFrame
#
#     @property
#     def _constructor_sliced(self):
#         return SubclassedSeries
#
#     def plot_all(self):
#         pass
#
#     @property
#     def base_class_view(self):
#         # use this to view the base class, needed for debugging in some IDEs. Note this just makes a new data frame
#         return pandas.DataFrame(self)


"""  -------------------------------------- tabular files --------------------------------------------------------   """


class TabularFile:
    def __init__(self):
        self._file_path = None
        self._file_header_rows = []    # a list of the file header lines as defined by the header line tags
        self._column_headers = []
        self._valid_column_headers = False
        self._header_rows_count = 0  # this is dynamic, the _snp_find_colum_headers will determine this
        self._header_line_tags = set()
        self.row_index_list = []    # in a plot these are the X values
        self.data_columns = []  # list of lists, each list is a column
        self._column_units = []  # list of units, lets try to use pint units, for some files this will not be known
        self.column_seperator = '\t'  # tab in interpreted as whitespace so .split() is called on each row

    def _extract_header(self):
        """ attempts to read the header and store it into the self._file_header_lines field """
        if self._file_path != '':
            try:
                with open(self._file_path) as tab_file_handle:
                    # file_iterator = csv.reader(tab_file_handle)
                    # for item in file_iterator:
                    #     line_str = item
                    #     if isinstance(item, list):
                    #         try:
                    #             line_str = item[0]
                    #         except IndexError:
                    #             line_str = ''
                    inner_break = False
                    for line_string in tab_file_handle:
                        for tag in self._header_line_tags:  # add the line to the headers
                            if tag in line_string:
                                self._file_header_rows.append(line_string)
                                log(f'header row: "{line_string}"')
                                break
                            elif line_string == '':
                                break    # ignore empty lines, keep iterating
                        else:
                            break
                            # inner_break = True
                        # if inner_break is True:
                        #     break
            except Exception as ex:
                raise Exception(f'cant load file with exception: "{ex}"')
        else:
            raise Exception(f'please pass a valid file path, received: {self._file_path}"')
        self.parse_header()

    @abc.abstractmethod
    def parse_header(self):
        """ takes the extracted headers and attempts to parse them according to the file type  """
        pass

    def _extract_data(self):
        """ iterates over the lines of the file  """
        if self._file_path != '':

            # determine the split char and some logic for later in the loop
            split_whitespace = False
            valid_whitespace = {'\t', ' ', '  ', '   ', '    ', ''}
            split_char = self.column_seperator  # used later in the loop
            if split_char in valid_whitespace:  # tab is whitespace so split on whitespace
                split_whitespace = True

            # open the iterator and start iterating the lines of the file
            try:
                with open(self._file_path) as tab_file_handle:
                    file_lines = tab_file_handle.readlines()
                    total_lines_in_file = len(file_lines)
                    # file_iterator = csv.reader(tab_file_handle)
                    header_lines_count = len(self.file_header_rows)
                    data_lines_count = total_lines_in_file - header_lines_count

                    # pre-allocate the columns
                    mem_space = float('NaN')
                    for column in self._column_headers:
                        self.data_columns.append([mem_space]*data_lines_count)
                    array_index = list(range(0, data_lines_count))

                    # skip past the header files in the iterator
                    data_lines = file_lines[header_lines_count:total_lines_in_file]
                    # for line, item in zip(range(header_lines_count), file_iterator):
                    #     pass    # iterates the file iterator past the header lines count

                    # after skipping the header start iterating the data
                    for column_index, line in zip(array_index, data_lines):  # type: int, str
                        # logic to split the string into each column element
                        if split_whitespace is True:   # tab is whitespace so split on whitespace
                            line_data_list = line.split()
                        else:   #
                            line_data_list = line.split(split_char)

                        # finally parse the row (list) of column elements ex: ['1.1', '2.2', ... 'n.n']
                        self.parse_data_line(column_index, line_data_list)
                    log(f'here')

            except Exception as ex:
                raise Exception(f'cant extract data with exception: "{ex}"')

    def parse_data_line(self, column_vertical_index: int, row_of_data: list):
        """ the default method uses the item at position 0 as the index and the rest of the items are columns"""
        for column_list, data in zip(self.data_columns, row_of_data):    # type: list, str
            if '!' in data:  # it is legal to add more comment rows in the data block for some reason
                self._column_headers.extend(data)   # if more comment rows are found, add them to the header
            else:
                column_list[column_vertical_index] = float(data)

    def read_file(self, file_path: str):
        """ reads the file into memory, it exists in python as a list of lists. Also loads metadata from the headeer
        if there is any """
        self._file_path = file_path
        self._extract_header()
        self._extract_data()

    def read_into_pandas_dataframe(self, file_path: str):
        """  reads the file into a pandas dataframe, clears the data from this class and returns the data frame"""
        self.read_file(file_path)
        # the index will be the frequency so grab that
        index_name = self._column_headers[0]
        index_values = self.data_columns[0]

        # the rest of the columns past the frequency is the sNp data
        col_names = self._column_headers[1:]
        col_data = self.data_columns[1:]

        # make the dict to load up the data frame
        data_dict = {col_name: col_data for col_name, col_data in zip(col_names, col_data)}
        d_frame = pandas.DataFrame(data_dict, index=index_values)
        d_frame.index.name = index_name
        return d_frame

    @property
    def header_line_tags(self):
        return self._header_line_tags

    @header_line_tags.setter
    def header_line_tags(self, value: set):
        self._header_line_tags = value

    @property
    def file_path(self):
        return self._file_path

    @file_path.setter
    def file_path(self, val: str):
        self._file_path = val

    @property
    def column_headers(self):
        return self._column_headers

    @column_headers.setter
    def column_headers(self, value: list):
        self._column_headers = value
        self._valid_column_headers = True   # if you set the headers we will go ahead and assume they are valid : )

    @property
    def header_row_count(self):
        return self._header_rows_count

    @header_row_count.setter
    def header_row_count(self, value: int):
        self._header_rows_count = value

    @property
    def file_header_rows(self):
        return self._file_header_rows

    # @file_header_rows.setter
    # def file_header_rows(self, value):
    #     self._file_header_lines = value


"""  -------------------------------------- sNp files ------------------------------------------------------------   """


class SNPFile(TabularFile):
    """ a class for reading working wth sNp or Touchstone files more info here;

    https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf

    Note that this class does not implement all features outlined in the specification """
    def __init__(self):
        super().__init__()
        self._frequency_units = None
        self._parameter = None
        self._format = None
        self._impedance = None
        self._valid_params = False
        self.header_line_tags = {'!', '#'}
        self._valid_colum_headers = False
        self._n_port_count = None    # the number of ports

    def read_file(self, file_path: str):
        path = Path(file_path)
        self._n_port_count = int(path.suffix[2])     # suffix looks like: '.s2p'
        log(f'Port Count: "{self._n_port_count}"')
        if self._n_port_count > 2:
            raise Exception(f'Not implemented for "{self._n_port_count}" port files')
        super().read_file(file_path)

    def parse_header(self):
        # find the params
        for line in self.file_header_rows:  # type: str
            if '#' in line:
                self._snp_find_options(line)
            if 's11' in line.lower():   # need to find something that is common to the column headers
                self._snp_find_colum_headers(line)
        if self._valid_colum_headers is False:
            # file probably does not have headers, need to generate them now
            prfx = self._parameter
            if prfx is not None:
                # need to make a header that is similar to [frequency, magS11, angS11, ... magSnn, angSnn]
                """ specifies the format of the network parameter data pairs. Legal values are:
                    DB for decibel-angle (decibel = 20 × log10|magnitude|)
                    MA for magnitude-angle,
                    RI for real-imaginary.
                    Angles are given in degrees. Note that this format does not apply to noise
                    parameters (refer to the “Noise Parameter Data” section later in this
                    specification). The default value is MA. 
                    """
                port_list = [val for val in range(1, self._n_port_count+1)]
                header_list_pre = []
                for port_a in port_list:
                    for port_b in port_list:
                        header_list_pre.append(f'{prfx}{port_b}{port_a}')
                l_case_format = self._format.lower()
                if l_case_format == 'db':
                    u1 = 'dBm'
                    u2 = 'ang'
                elif l_case_format == 'ma':
                    u1 = 'mag'
                    u2 = 'ang'
                elif l_case_format == 'ri':
                    u1 = 're'
                    u2 = 'im'
                else:
                    raise Exception(f'cant determine column names from format: "{l_case_format}" ')
                log(f'header list pre: "{header_list_pre}"')
                final_header = [f'{self._frequency_units}']
                for item in header_list_pre:
                    final_header.extend([f'{u1}{item}', f'{u2}{item}'])
                log(f'header list final: "{final_header}"')
                self._column_headers = final_header


    def _snp_find_options(self, row_in: str):
        """
        Example options line: # hz S ma R 11

        # <frequency unit> <parameter> <format> R <n>

        frequency unit:
            specifies the unit of frequency. Legal values are
            GHz, MHz, KHz, Hz. The default value is GHz.
        parameter:
            specifies what kind of network parameter data is
            contained in the file. Legal values are:
            S for Scattering parameters,
            Y for Admittance parameters,
            Z for Impedance parameters,
            H for Hybrid-h parameters,
            G for Hybrid-g parameters.
            The default value is S
        format:
            specifies the format of the network parameter data
            pairs. Legal values are:
            DB for dB-angle (dB = 20*log10|magnitude|)
            MA for magnitude-angle,
            RI for real-imaginary.
            Angles are given in degrees. Note that this format
            does not apply to noise parameters. (Refer to the
            “Adding Noise Parameters” section at the end of this
            document). The default value is MA.
        R n:
            specifies the reference resistance in ohms, where n
            is a positive number of ohms (the real impedance to
            which the parameters are normalized). The default
            reference resistance is 50 ohms.
        """
        options = row_in.split()  # example: ['#', 'hz', 'S', 'ma', 'R', '11']
        if options[0] == '#' and len(options) == 6:   # this is the good case, its well formatted
            self._frequency_units = options[1]
            self._parameter = options[2]
            self._format = options[3]
            self._impedance = options[5]
            self._valid_params = True
            log(f'options: "{options}"')

    def _snp_find_colum_headers(self, row_in: str):
        row_sections = row_in.split()
        removed_line_start_char = row_sections.pop(0)
        if len(removed_line_start_char) > 1:    # sometimes there is no space after the !
            row_sections.insert(0, f'{removed_line_start_char[1:]}')
        if len(row_sections) > 1:   # for clearing empty comment lines
            # if row_sections[1] == '':   # remove extra spaces
            #     row_sections = [item for item in row_sections if item != '']
            if len(row_sections) > 1:  # for clearing empty comment lines
                first = row_sections.pop(0).lower()
                if 'f' in first.lower():   # this is good, its probably the header typical is: f, F, freq
                    self._column_headers = [f'Frequency {self._frequency_units}']
                    for section in row_sections:
                        self._column_headers.append(section)
                    self._valid_colum_headers = True

    def get_mag_db_re_column_names(self):
        """ Since the format can be in DB MA or RI this method returns the colum names for D, M, or R respectively """

    # def read_snp_file(self, n=2):
    #     if n == 2:
    #         self._file_path = request_user_select_file()
    #
    #         # ----- using builtin lib 'csv' ---------
    #
    #         with open(file_path, newline='') as file:
    #
    #             # dialect = csv.Sniffer().sniff(file.read(1024))
    #             # file.seek(0)
    #             reader = csv.reader(file)
    #             self._snp_find_options(reader)
    #             if self._valid_params is True:
    #                 self._snp_find_colum_headers(reader)
    #
    #                 csv_string = ''
    #
    #                 for row in reader:
    #                     if '!' not in row[0] or '#' not in row[0]:
    #                         csv_string += f"{row[0]}\n"
    #                 string_io = StringIO(csv_string)
    #                 data_frame = pandas.read_csv(string_io, names=self._column_headers, sep='\t')
    #                 log(f'data frame: "{data_frame.to_string()}"')
    #                 for index, row in data_frame.iterrows():
    #                     log(f'row: {row}, index: {index}')
    #
    #             else:  # probably not worth continuing
    #                 log(f'Could not load parameters')
    #
    #         # ------ using pandas ---------


"""  ---------------------------------  Example Code Below -------------------------------------------------------   """


def request_user_select_file(win_title='please select a file'):
    tkinter.Tk().withdraw()  # prevents an empty tkinter window from opening
    file = Path(filedialog.askopenfilename(title=win_title))
    if file.exists():
        return str(file)
    else:
        return None


if __name__ == '__main__':

    # file_path_str = request_user_select_file()
    file_path_str = f'/Users/joeeveryman/PycharmProjects/scikit-rf/skrf/tests/ntwk_arbitrary_frequency.s2p'
    if file_path_str is not None:
        # file = SNPFile()
        # frame = file.read_into_pandas_dataframe(file_path_str)
        # column_tag = 'res'
        # columns_to_plot = [item for item in file.column_headers if column_tag in item.lower()]
        # frame.plot(y=columns_to_plot)
        # py_plot.show()

        open_file = open(file_path_str)
        scikit_snp_file = skrf.Touchstone(file_path_str)
        scikit_snp_file.load_file(open_file)
        rf_net_a = skrf.Network(file_path_str)
        net_data_frame = skrf.network_2_dataframe(rf_net_a, )   # type: pandas.DataFrame
        net_data_frame.plot(y=net_data_frame.columns)
        py_plot.show()
        log(f'here')

    # file.read_snp_file(2)


