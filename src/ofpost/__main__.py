'''
MAIN PROGRAM.
'''
import sys


# ------------------ IMPORT OPTIONS ------------------
import ofpost.options as opt


# ------------------ IMPORT FUNCTIONS ------------------
from ofpost.lib import find_files, vtk2image, read_dat, read_forces



# ------------------ MAIN PROGRAM ------------------
# parse custom user options
opt.parse_options()

# look for files to be analyzed in each path
for path in opt.paths:
    # update working path
    opt.working_path = path

    # analyze .vtk files
    for vtk_file in find_files(opt.VTK_FILE, path,
                               exceptions=[opt.CLOUD_FILE]):
        vtk2image(vtk_file)

    # analyze .dat and .xy files
    for res_file in find_files(opt.RES_FILE, path):
        read_dat(res_file, semilogy=True, append_units=False)

    for dat_file in find_files(opt.DAT_FILE, path,
                               exceptions=[opt.RES_FILE, opt.FORCE_FILE]):
        read_dat(dat_file)

    for xy_file in find_files(opt.XY_FILE, path):
        read_dat(xy_file)

    for force_file in find_files(opt.FORCE_FILE, path):
        read_forces(force_file)

sys.exit(0)
