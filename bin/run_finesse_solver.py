from __future__ import print_function, division, absolute_import
#from future.builtins import input
from distutils.util import strtobool
#import sys
import time
import argparse
#sys.path.append("../")
import numpy as np
from fabry.tools.file_io import read_Ld_results
from os.path import abspath, join
from mpi4py import MPI

if __name__ == "__main__":
    print('im here in the start of the run finesse solver script')
    start_time = time.time()
    Comm = MPI.COMM_WORLD
    rank = Comm.Get_rank()
    if rank == 0:
        parser = argparse.ArgumentParser(description='Runs a finesse solver')
        parser.add_argument('folder', type=str,
                            help='folder containing finesse input files')
        parser.add_argument('ld_folder', type=str,
                            help='folder containing L d wavelength calibration results')
        parser.add_argument('filter_type', type=str,
                            help='Name of filter (Ar, He, ar, he, ...)')
        parser.add_argument('--restart', action='store_true', default=False,
                            help="Set to True if you want MultiNest to start over instead of resuming")
        args = parser.parse_args()

        if args.filter_type.lower() in ['ar', 'argon', '488']:
            filter_type = 'argon'
        elif args.filter_type.lower() in ['he', 'helium', '468.6']:
            filter_type = 'helium'
        else:
            print('Filter {0:s} not recognized.'.format(args.filter_type))
            sys.exit(1)

        folder = abspath(args.folder)

        prior_filename = join(folder, 'finesse_prior_info.json')
        data_filename = join(folder, 'finesse_input.h5')

        # Lpost, dpost = read_Ld_results(abspath(args.ld_folder))
        Lpost = 0.0
        dpost = 0.0
        #Ldpost = np.loadtxt(join(abspath(args.ld_folder), 'full_post_equal_weights.dat'), ndmin=2)
        #Lpost = Ldpost[:, 0]
        #dpost = Ldpost[:, 1]

        restart = args.restart
        if restart:
            a = raw_input("Are you sure you want to restart? ")
            try:
                a = bool(strtobool(a))
            except ValueError:
                print("invalid input exiting...")
                sys.exit(1)

            if a:
                print("ok moving on with restart")
                restart = True
            else:
                print("Ok, overwriting restart to False")
                restart = False

        solver_in = {'prior_fname': prior_filename,
                     'data_fname': data_filename,
                     'Lpost': Lpost,
                     'dpost': dpost,
                     'filter': filter_type,
                     'restart': restart,
                     'out_folder': folder,
                     }

    else:
        solver_in = None

    solver_in = Comm.bcast(solver_in, root=0)

    if solver_in is not None:
        if solver_in['filter'] == 'argon':
            from fabry.finesse.argon_solver import solver, full_solver
        elif solver_in['filter'] == 'helium':
            from fabry.finesse.helium_solver import full_solver
        else:
            print("No idea how you got here...")
            sys.exit(1)
        resume = not solver_in['restart']
        # solver(solver_in['out_folder'], solver_in['prior_fname'], solver_in['data_fname'],
        #        solver_in['Lpost'], solver_in['dpost'], resume=resume, test_plot=False)

        full_solver(solver_in['out_folder'], solver_in['prior_fname'], solver_in['data_fname'],
                resume=resume, test_plot=False)
        #full_solver(solver_in['out_folder'], solver_in['data_fname'],
        #            resume=resume, test_plot=False)
    if rank == 0:
        end_time = time.time()
        print("Total Time Elasped: {} minutes".format((end_time - start_time) / 60.0))
        if solver_in['filter'] == 'argon':
            from fabry.finesse.check_argon_solver import check_solver, check_full_solver
        #     pass
        # elif solver_in['filter'] == 'helium':
        #     print("still working on implementing the helium check solver")
        else:
            print("No idea how you got here...")
            sys.exit(1)

        #check_solver(solver_in['out_folder'], solver_in['Lpost'], solver_in['dpost'])
        check_full_solver(solver_in['out_folder'])

    # folder = "../Data/2018_04_23/Argon3"

    # prior_filename = join(folder, 'finesse_prior_info.json')
    # data_filename = join(folder, 'finesse_input.h5')

    # Lpost, dpost = read_Ld_results(folder)

    # ar_solver.solver(prior_filename, data_filename, Lpost, dpost)
