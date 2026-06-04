from os import getenv, path
import zipfile
import logging

DEBUG=getenv("DEBUG", 'False').lower() in ('true', '1', 't', True)

def debug_print(x)->None:
    logging.log(logging.DEBUG, x)


def add_prefix_to_filename(full_path: str, prefix: str = "", prefix_sep: str = "_") -> str:
    """Return full_path with prefix applied only to the filename part."""
    
    if len(prefix) == 0:
        return full_path
    
    if prefix[-1] != prefix_sep:
        prefix += prefix_sep 

    dir_name, file_name = path.split(full_path)
    prefixed_name = prefix + file_name
    if dir_name:
        return path.join(dir_name, prefixed_name)
    return prefixed_name


def write_zipfile(zipfile_path: str, zip_files: list[str])->str:
    """given list of files and zip file path, create and save
    a zip file.  The items in the zip file have their directory 
    stripped so unzipping will go directly into the target folder
    
    SIDE EFFECT: files written to disk

    Args:
        zipfile_path (str): where to store the zip file
        zip_files (list[str]): list of full paths to files to include
    Returns:
        str: path to zip file saved
    """
    shape_zip = zipfile.ZipFile(zipfile_path, 'w')

    tmp_str = []
    for zfile in zip_files:
        tmp_str = zfile.rsplit('/',1)
        tmp_loc_file = tmp_str[1]
        shape_zip.write(zfile, arcname=tmp_loc_file, compress_type=zipfile.ZIP_DEFLATED)

    shape_zip.close()
    return(zipfile_path)


######## FILE WRITING #############
def write_setback_text_table(text_file_name: str, table_text: str)->str:
    """write text file of set-back distances in tabular form by direction

    Args:
        text_file_name (str): file name to save the table as
        D (np.ndarray): array of setback distances
        
    Returns:
        str: file name that was saved
    """ 

    with open(text_file_name, 'wt') as f_handle:
        f_handle.write(table_text)

    return(text_file_name)

############ dealing with file types

def is_hdf5_file_name(file_name:str)->bool:
    """is this file named like it might be an hdf5 file?

    Args:
        file_name (str): string of file name
    Returns:
        bool: True if the file name suggests it might be an hdf5 file, False otherwise
    """
    
    extension:str = path.splitext(file_name)[-1]
    if extension.lower() in ['.h5', 'hdf5', 'hf5']:
        return True
    return False

def is_json_file_name(file_name:str)->bool:
    """is this file named like it might be a JSON file?

    Args:
        file_name (str): string of file name
    Returns:
        bool: True if the file name suggests it might be a JSON file, False otherwise
    """
    extension:str = path.splitext(file_name)[-1]
    if extension.lower() == '.json':
        return True
    return False