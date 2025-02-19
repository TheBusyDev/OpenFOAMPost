'''
LIBRARY FUNCTIONS.
'''
import re
import traceback
import numpy as np
import pandas as pd
import pyvista as pv
import matplotlib.pyplot as plt
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Generator 


# ------------------ IMPORT CONSTANTS ------------------
from ofpost import EXTENSION, UNITS_OF_MEASURE, COMPONENTS_EXT, MAGNITUDE_EXT, \
                   CAMERA_ZOOM, COLORMAPS, DEFAULT_COLORMAP, \
                   PLOTTER_OPTIONS, SCALAR_BAR_ARGS, MESH_ARGS, \
                   IS_STEADY, FIGURE_ARGS, FORCE_LABEL, MOMENT_LABEL



# ------------------ FUNCTIONS ------------------
def find_files(pattern: str, path: Path, exceptions: list[str]=[]) -> Generator[Path, None, None]:
    '''
    Look for files based on specified pattern recursively. \\
    In 'pattern', '*' matches any string. \\
    'exceptions' is a list of patterns to be excluded. \\
    Return filepaths as generator. \\
    Print error message if no file is found.
    '''
    print(f'\nLooking for {pattern} files in {path.absolute()}...')
    is_found = False

    # look for files that match 'pattern'
    for root, _, files in path.walk(top_down=True):
        for file in files:
            file = Path(file)

            # skip other files
            if not file.match(pattern, case_sensitive=False):
                continue

            # skip exceptions
            if any([file.match(exc, case_sensitive=False) for exc in exceptions]):
                continue
            
            # yield filepath
            filepath = root / file
            is_found = True
            yield filepath

    if not is_found:
        print(f'No {pattern} file found.')


def read_file_decorator(read_file: Callable) -> Callable:
    '''
    Decorator to be applied to read-file functions.
    '''
    def wrapper(filepath: Path, **kwargs) -> Any:
        print(f'\nProcessing {filepath}...')

        try:
            return read_file(filepath, **kwargs)
        except Exception as e:
            print(f'ERROR: unable to process {filepath.name}:')
            traceback.print_exception(e)
    
    return wrapper


def get_output_filepath(filepath: Path, filesuffix: str='') -> tuple[Path, str, str, str]:
    '''
    Return output filepath (with extension), input filename, timestep and output directory name. \\
    If 'filesuffix' is provided, then files will be generated with the specificed suffix.
    '''
    # get timestep and output path based on OpenFOAM convention
    # (under postProcessing folder)
    filename = filepath.stem # filename without extension
    timestep = filepath.parent.name # get timestep from directory name

    try:
        float(timestep) # verify that timestep is really a float
    except ValueError:
        timestep = '0'

    # create output file path
    outpath = filepath.parent.parent # output path
    outdirname = outpath.name # output directory name
    outfilename = filename # output filename

    if filesuffix != '':
        # remove illegal characters from filesuffix
        filesuffix = filesuffix.replace('/', '')
        filesuffix = filesuffix.replace('\\', '')
        filesuffix = filesuffix.replace(' ', '')
        # add filesuffix to output filename
        outfilename += '_' + filesuffix

    if timestep != '0':
        outfilename += '_' + timestep # add timestep to output filename
    
    outfilename += EXTENSION # add extension to output filename
    outfilepath = outpath / outfilename # output file path
    print(f'Output file: {outfilepath}')

    return outfilepath, filename, timestep, outdirname


def get_units(array_name: str) -> str:
    '''
    Get units of measurement based on input array. \\
    Return empty string if array is not found.
    ''' 
    # detect units of measurement
    try:
        units = ' [' + UNITS_OF_MEASURE[array_name] + ']'
        return units
    except KeyError:
        pass

    # try to extract array_name
    match = re.search(r'\((.*?)\)', array_name)

    if match != None:
        array_name = match.group(1)

        # try again to detect units of measurement
        try:
            units = ' [' + UNITS_OF_MEASURE[array_name] + ']'
            return units
        except KeyError:
            pass

    # remove extension from components
    for comp in COMPONENTS_EXT:
        if array_name.endswith(comp):
            array_name = array_name.removesuffix(comp)
            break
    
    # try again to detect units of measurement
    try:
        units = ' [' + UNITS_OF_MEASURE[array_name] + ']'
    except KeyError:
        units = ''

    return units


def adjust_camera(plotter: pv.Plotter) -> None:
    '''
    Try to infer slice normal direction and adjust plotter camera position. \\
    If normal direction is not computed correctly \\
    or slice is not aligned with x, y or z direction, then just reset camera.
    '''
    mesh = plotter.mesh

    # try to infer slice normal direction (slice has zero thickness in normal direction)
    bounds = np.array(mesh.bounds)
    delta_bounds = np.abs(bounds[1::2] -  bounds[0:-1:2])
    normal_idx, = np.where(delta_bounds < 1e-16) # get zero-thickness direction
    
    # return if normal is not found correctly
    if len(normal_idx) != 1:
        plotter.reset_camera()
        return
    
    # generate normal vector
    normal = np.zeros(3)
    normal[normal_idx] = 1

    # set up the camera position and focal point
    camera_position = mesh.center + normal
    focal_point = mesh.center

    # compute camera view-up orientation
    delta_bounds[normal_idx] = np.inf # needed to avoid the normal direction as view-up direction
    min_bound = np.min(delta_bounds)
    min_indices, = np.where(delta_bounds == min_bound)
    view_up_idx = min_indices[-1] # get view-up direction
    view_up = np.zeros(3)
    view_up[view_up_idx] = 1 if view_up_idx != 2 else -1

    plotter.camera_position = [
        camera_position,
        focal_point,
        view_up
    ]

    plotter.reset_camera() # camera is reset automatically based on mesh bounds
    plotter.zoom_camera(CAMERA_ZOOM)


@read_file_decorator
def vtk2image(filepath: Path) -> None:
    '''
    Load .vtk file and convert it to image format as specified by the user.
    '''
    # load VTK file and get array names contained inside it
    mesh = pv.read(filepath)

    if len(mesh.cell_data) > 0:
        print('Loading cell data...')
        data = mesh.cell_data # load cell data as preferred option
    elif len(mesh.point_data) > 0:
        print('Loading point data...')
        data = mesh.point_data # load point data as alternative
    else:
        raise ValueError('ERROR: empty file.')
    
    array_names = data.keys().copy()
    colormaps = {}

    # loop around all the arrays found in mesh
    for array_name in array_names:
        array = data[array_name]

        # remove empty arrays
        if len(array) == 0:
            data.pop(array_name)
            continue

        # detect units of measurement
        units = get_units(array_name)

        # detect array colormap
        try:
            array_cmap = COLORMAPS[array_name]
        except KeyError:
            array_cmap = DEFAULT_COLORMAP
        
        # detect 3D arrays
        if array.shape[-1] == 3:
            # split arrays in their components 
            for index, comp in enumerate(COMPONENTS_EXT):
                new_name = array_name + comp + units
                data[new_name] = array[:, index]
                colormaps[new_name] = array_cmap # add entry to colormap for each component

            # rename array to indicate its magnitude
            new_name = array_name + MAGNITUDE_EXT + units
        else:
            # add units of measurements to the array
            new_name = array_name + units
        
        # rename array and add entry to colormap
        data[new_name] = data.pop(array_name)
        colormaps[new_name] = array_cmap
    
    # create a new plotter for pyvista, load mesh and adjust camera
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(mesh)
    adjust_camera(plotter)
    plotter.show_axes()
    plotter.clear()

    # adjust plotter options
    for key, value in PLOTTER_OPTIONS.items():
        setattr(plotter, key, value)

    # loop around the modified arrays
    for array_name in data.keys():
        # plot array and set plot properties
        plotter.add_mesh(mesh,
                         scalars=array_name,
                         cmap=colormaps[array_name],
                         scalar_bar_args=SCALAR_BAR_ARGS,
                         **MESH_ARGS)

        # remove units from array name
        array_name = re.sub(r'\[.*?\]', '', array_name)
        array_name = re.sub(r'\s+', '', array_name)

        # create output directory and export mesh as image
        outfilepath, *_ = get_output_filepath(filepath, filesuffix=array_name)

        try:
            plotter.screenshot(outfilepath)
        except ValueError:
            plotter.save_graphic(outfilepath)
        
        # clear plotter before starting a new loop
        plotter.clear()
    
    plotter.close() # close plotter


def read_labels(filepath: Path) -> list[str]:
    '''
    Get labels from file (i.e. the last comment line).
    '''
    with open(filepath, 'r') as file:
        for line in file:
            # skip comment lines
            if line == '' or line[0] != '#':
                break

            orig_labels = line
    
    try:
        # manipulate labels
        orig_labels = orig_labels.strip()
        orig_labels = orig_labels.removeprefix('#')
        orig_labels = orig_labels.split() # original version of labels
    except:
        return [] # return empty list if any error occured

    # create labels list
    labels = []

    for label in orig_labels:
        # do not append units of measurement
        if not re.match(r'\[.*\]', label):
            labels.append(label)
        else:
            labels[-1] += f' {label}' # append units at the end of the latest label

    return labels


def plot_data(df: pd.DataFrame, filepath: Path, semilogy: bool=False, append_units: bool=True, filesuffix: str='') -> None:
    '''
    Plot data from .dat files and save figure. \\
    Receive pandas DataFrame and source filepath as input.
    '''
    # create new plot
    x = df.iloc[:,0]

    if IS_STEADY and x.name == 'Time':
        x.name = 'Iterations'

    fig = plt.figure(**FIGURE_ARGS)

    # loop around DataFrame
    for label, y in df.iloc[:, 1:].items():
        # append units of measurement
        if append_units:
            label += get_units(label)

        # plot data from DataFrame
        if not semilogy:
            plt.plot(x, y, label=label)
        else:
            plt.semilogy(x, y, label=label)

    outfilepath, filename, timestep, outdirname = get_output_filepath(filepath, filesuffix)

    # set plot title
    title = outdirname

    if timestep != '0':
        title += '@' + timestep + UNITS_OF_MEASURE['Time'] # add timestep to plot title
        title += ' (' + filename + ')' # add filename info to plot title

    # set plot xlabel
    xlabel = x.name + get_units(x.name)
    
    # set plot properties
    plt.title(title)
    plt.xlabel(xlabel)
    plt.grid()
    plt.legend()

    # save figure
    plt.savefig(outfilepath)
    plt.close(fig) # close figure once it's saved


@read_file_decorator
def read_dat(filepath: Path, semilogy: bool=False, append_units: bool=True) -> None:
    '''
    Read data from .dat files \\
    (for 'forces.dat' files, refer to 'read_forces' function).
    '''
    # initialize labels
    labels = read_labels(filepath)

    # retrive data from yPlus.dat file
    data = pd.read_csv(filepath, 
                       comment='#',
                       delimiter=r'\t+|\s+',
                       engine='python',
                       names=labels) # set labels
    
    # plot data and save image
    if 'patch' not in data.columns:
        plot_data(data, filepath, semilogy, append_units)
        return

    # get patch and time DataFrames
    patches = data['patch'].drop_duplicates()
    time = data['Time'].drop_duplicates()
    time.reset_index(drop=True, inplace=True)

    # define field name from filename (without extension)
    field = filepath.stem

    # find columns
    target_columns = ['min', 'max', 'average']
    old_columns = []

    for col in data.columns:
        if any([col.startswith(tc) for tc in target_columns]):
            old_columns.append(col)
    
    new_columns = [f'{field} {col}' for col in old_columns]

    # rename columns inside DataFrame
    columns = {old_col: new_col
               for old_col, new_col in zip(old_columns, new_columns)}
    data.rename(columns=columns, inplace=True)

    # loop around all the columns
    for col in data.columns:
        # skip useless columns
        if col in ['Time', 'patch']:
            continue

        new_data = time # initialize new DataFrame

        # extract patch data and rename columns for each patch
        for patch in patches:
            # extract patch data
            patch_data = data.loc[data['patch'] == patch]
            patch_data = patch_data[col]

            # insert patch name to column name
            patch_data.name = f'{patch} {patch_data.name}'
            patch_data.reset_index(drop=True, inplace=True)

            # concatenate new data
            new_data = pd.concat([new_data, patch_data], axis=1) 

        # plot selected data
        plot_data(new_data, filepath, semilogy, append_units, filesuffix=col)


@read_file_decorator
def read_forces(filepath: Path) -> None:
    '''
    Read data from 'forces.dat' files and save plot.
    '''
    # open force file
    with open(filepath, 'r') as file:
        content = file.read()
    
    # get contributions of each force 
    # (up to 3 contributions: pressure, viscosity, porosity)
    contribs = re.search(r'forces\((.*?)\)', content)

    try:
        n_contribs = len(contribs.group(1).split()) # number of contributions
    except:
        n_contribs = 0

    # remove all the bracket
    content = content.replace('(', ' ')
    content = content.replace(')', ' ')
    dummy_file = StringIO(content)

    data = pd.read_csv(dummy_file,
                       comment='#', 
                       delimiter=r'\t+|\s+',
                       engine='python')

    def sum_contribs(start_index: int, label: str, n_contribs: int) -> pd.DataFrame:
        # initialize DataFrame and save Time to DataFrame
        df = pd.DataFrame()
        df['Time'] = data.iloc[:,0]

        # sum contributions from pressure, viscosity and porosity
        indices = range(start_index, start_index+3)
        labels = [label + comp for comp in COMPONENTS_EXT]

        for index, label in zip(indices, labels):
            sum_axes = [index + 3*n for n in range(n_contribs)] # get axes to be summed
            df[label] = data.iloc[:, sum_axes].sum(axis=1)
        
        return df

    # get forces and save plot
    start_index = 1
    forces = sum_contribs(start_index, FORCE_LABEL, n_contribs)
    plot_data(forces, filepath, filesuffix='forces')

    # get moments and save plot
    start_index = 1 + 3*n_contribs
    moments = sum_contribs(start_index, MOMENT_LABEL, n_contribs)
    plot_data(moments, filepath, filesuffix='moments')