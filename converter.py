import os
import re
import collections
import json
import pprint
import yaml
import pandas
import tkinter as tk
from tkinter import filedialog
from tkinter.filedialog import askopenfilename


def df2dict(df: pandas.DataFrame) -> dict:
    """Returns the dict by matching key1 of the dataframe to key2 as value."""
    _dict = {}
    key1, key2 = df.keys()
    for i in range(0, len(df)):
        row = df.iloc[i]
        _dict[row[key1]] = row[key2]
    return _dict


def get_symbol_definitions(symbol_file: str) -> dict:
    """Returns the symbol definitions by searching the YAML file.
    
    Parameters
    ----------
    symbol_file: str
        path of the yaml file containing definitions.
    """
    symbol_defs = {}

    yaml_fp = open(symbol_file, "r")
    yaml_data = yaml.load(yaml_fp, Loader=yaml.FullLoader)
    yaml_fp.close()
    cols = list(yaml_data['materials']['Aluminum 6061-T6']['Basic Information'].keys())
    cols_with_symbols = cols[cols.index('References')+1:]

    # Iterate over each title to get definitions
    for col in cols_with_symbols:
        appeared = False
        defs = yaml_data['materials']['Aluminum 6061-T6']['Basic Information'][col]['Default']
        defs_copy = defs.copy()

        # Delete all the data after and including 'Hash' key 
        # because it doesn't contain definitions of symbols
        for key in defs.keys():
            if key == 'Hash': appeared=True
            if (appeared) or (key == 'file'):
                del defs_copy[key]

        for d in defs_copy: 
            symbol_defs[defs_copy[d]['Symbol']] = d  # copy the title and it's symbol definitions to symbol_defs

    return symbol_defs


def dump_symbols(symbol_defs: dict, output_file: str):
    """Dumps the symbols into a json file for later use."""
    fp = open(output_file, "w")
    json.dump(symbol_defs, fp, indent=4)
    fp.close()

    
def retrieve_symbols(symbol_file: str) -> dict:
    """Retrieves the symbols from the json file."""
    fp = open(symbol_file, "r")
    symbols = json.load(fp)
    return symbols


def attach_extra_data(main_data: collections.OrderedDict, 
                    extra_data: collections.OrderedDict, 
                    material: str):
    """Attaches extra data to the basic information section of the main_data.
    
    Parameters
    ----------
    main_data: collections.OrderedDict
        Main data where extra data will be attached.
    
    extra_data: collections.OrderedDict
        Extra data which will be attached to main data.
        
    material: str
        Title of the material on which this data will be attached.
    """
    for key in extra_data:
        main_data['materials'][material]['Basic Information'][key] = extra_data[key]
        
        
def get_extra_data(ref_yaml_file: str) -> collections.OrderedDict:
    yaml_fp = open(ref_yaml_file, "r")
    yaml_data = yaml.load(yaml_fp, Loader=yaml.FullLoader)
    yaml_fp.close()
    
    basic_info = yaml_data['materials']['Aluminum 6061-T6']['Basic Information']

    extra_data = collections.OrderedDict()
    extra_data_keys = list(basic_info.keys())

    for i in range(1, extra_data_keys.index('References')+1):
        extra_data[extra_data_keys[i]] = basic_info[extra_data_keys[i]]

    return extra_data


def save_yaml(filename: str, data: dict):
    yaml_fp = open(filename, "w")
    yaml.dump(data, yaml_fp,  default_flow_style=False)



if __name__ == "__main__":

    root = tk.Tk()
    root.withdraw() 
    input_file = filedialog.askopenfilename(title = "Select Base file",
            filetypes = (("text file","*.txt"),("all files","*.*")))

    #pp = pprint.PrettyPrinter(indent=4) # pretty printer
    FILE_PATH = input_file
    SYMBOL_FILE     = "symbols.json"
    RAW_SYMBOL_FILE = "Newformat.yaml"

    symbols: dict = {}

    # If file containing symbols do not exists then get the symbols 
    # from raw file and then process and output it for next use.
    if os.path.exists(SYMBOL_FILE):
        symbols = retrieve_symbols(SYMBOL_FILE)
    else:
        symbols = get_symbol_definitions(RAW_SYMBOL_FILE)
        dump_symbols(symbols, output_file=SYMBOL_FILE)
        
    extra_data = get_extra_data(RAW_SYMBOL_FILE)

    # Get all the mappings for eos and mat values
    eos_df = pandas.read_csv("eos_types.csv", encoding="utf-8")
    eos_map = df2dict(eos_df)

    mat_df = pandas.read_csv("mat_types.csv", encoding="utf-8")
    mat_map = df2dict(mat_df)

    data = collections.OrderedDict()
    data['materials'] = {}

    global mat_title, current_key
    prev_line_titles = []
    mat_title=None
    current_key = '' # current eos or mtyp mapped value running

    mat_types = []
    eos_types = []

    # open the file

    MATERIAL_SEPERATOR = '!--------------------------------------------------------------------------------------'
    SEPERATOR = '!--------------------------- MID       MTYP    Density   Title ------------------------'
    EOS_SEPERATOR = '!------------------------- EOSID     EOSTYP      Title --------------------------------'

    want = None

    fp = open(FILE_PATH, "r") # file pointer

    ptr   = 0    # line pointer for file
    start = 0    # start limit
    stop  = None   # stop limit

    prop_ext_started = False # if turned on then process of extracting properties begin
    prev_blank_pos = [] # positions at which blank appeared in previous line

    mtyp_marker = -1  # marks the line of mtyp types
    mat_marker  = -1  # marks the line when material title appears
    eos_marker  = -1

    marked = -1 # line value of which was marked previously

    for line in fp.readlines():
        if (start != None) and (ptr < start) : ptr += 1;continue
        if (stop  != None) and (ptr == stop) : break
            
        if line == "\n" : prop_ext_started = False
            
        if prop_ext_started:
            if line.startswith("!"):
                syms = [sym.strip() for sym in line.strip().split(" ")] # symbols 
                syms = [sym for sym in syms if sym not in ['', '!']]
                
                temp = syms[:] # copy the syms list
                # delete blanks by storing their positions in a list
                for i in range(0, len(temp)):
                    if temp[i] == 'blank':
                        del syms[syms.index('blank')]
                        prev_blank_pos.append(i)
                
                for key in syms:
                    try:
                        title = symbols[key]
                    except:
                        title = key
                    prev_line_titles.append(title)
                    data['materials'][mat_title]['Basic Information'][current_key]['Default'][title] = {
                        'Value':'None', 'Symbol':key
                    }
                del temp
                  
            else:
                vals = [sym.strip() for sym in line.strip().split(" ") if sym.strip() != '']
                
                temp = vals[:] # copy whole vals list
                for i in range(0, len(temp)):
                    if i in prev_blank_pos:
                        #print(f"Deleting {vals[vals.index(temp[i])]}")
                        del vals[vals.index(temp[i])]
                    
                for i in range(0, len(prev_line_titles)):
                    data['materials'][mat_title]['Basic Information'][current_key]['Default'][prev_line_titles[i]]['Value'] = float(vals[i])

                prev_blank_pos.clear() # empty the prev pos list
                prev_line_titles.clear() # empty the prev line titles

        
        # ****************** CHECK IF LINE IS MARKED BY ANY MARKER ********************
        # -----------------------------------------------------------------------------
        # mtyp marker
        if ptr == mtyp_marker: 
            splitted_line = line.strip().split(" ")[2:]
            row = [word.strip() for word in splitted_line if word != ""]
            
            material_id = row[0]
            mtyp        = row[1]
            density     = row[2]
            title       = row[3]
            mat_types.append(row)
            
            mtyp_value = mat_map[int(mtyp)].strip().strip(":")
            
            mat_type_str = f"MTYP {mtyp} {mtyp_value}"        
            
            data['materials'][mat_title]['Basic Information']['Mats&EOS']['Material Types'][mat_type_str] = {
                "Title":title,
                "MID":material_id,
                "Density":density
            }
            data['materials'][mat_title]['Basic Information'][mtyp_value] = {"Default":{}}
            current_key = mtyp_value
            prop_ext_started = True
        # -----------------------------------------------------------------------------
        # material marker
        elif ptr == mat_marker:
            mat_title = line.replace('! ', '').strip()
            data['materials'][mat_title] = {'Hash'           : 'N/A',
                                            'Parent Hash'    : 'N/A',
                                            'Last Revision'  : 'N/A',
                                            'Keywords'       : 'N/A',
                                            'Basic Information':{
                                                'Mats&EOS':{
                                                    'Material Types':{},
                                                    'EOS Types':{},
                                            }
                                        }
                                        }
            
            # Attach extra information
            attach_extra_data(data, extra_data, mat_title)
            marked = ptr  
        # -----------------------------------------------------------------------------
        # eos marker
        elif ptr == eos_marker:
            splitted_line = line.strip().split(" ")[2:]
            row = [word.strip() for word in splitted_line if word != ""]
            
            eos_id    = row[0]
            eos_typ   = row[1]
            eos_title = row[2]
            eos_types.append(row)
            
            eos = eos_map[int(eos_typ)].strip().strip(":")
            eos_type_str = f"Type {eos_typ} {eos}"
            data['materials'][mat_title]['Basic Information']['Mats&EOS']['EOS Types'][eos_type_str] = {
                "Title":title,
                "EOSID":eos_id,
            }
            
        # ******* CHECK IF LINE MATCHES ANY SEPERATORS THEN MARK THE NEXT LINE **********
        # mtyp seperator
        if (line.strip() == SEPERATOR):
            mtyp_marker = ptr + 1
        
        # material seperator
        elif (line.strip() == MATERIAL_SEPERATOR):
            if (ptr != 0) and (marked == ptr-1) : mat_marker = -1
            else : mat_marker = ptr + 1
            
        # eos seperator
        elif (line.strip() == EOS_SEPERATOR):
            eos_marker = ptr + 1
            
        ptr += 1

    fp.close()

    output_file = "output.yaml"
    save_yaml(output_file, data)

    print(f"[+] Data sucessfully saved to {output_file}")
