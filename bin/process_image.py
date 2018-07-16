from __future__ import division, absolute_import
import sys
sys.path.append("../")
from os.path import join, abspath
import argparse
import numpy as np
from fabry.tools import images, plotting, file_io
from fabry.core import fitting, ringsum
import matplotlib.pyplot as plt
import h5py 
from scipy.stats import norm


def remove_prof(r, sig, sig_sd, pk_guess=None, poly_num=5):
    '''
    removes a polyfit of order minima from ringsum

    Args:
        r (np.ndarray): binarr of ringsum
        sig (np.ndarray): ringsum to be subtracted
        poly_num (int, default=5): order used for polyfit

    Returns:
        peak_loc (np.ndarray): peak locations in r
        poff (np.ndarray): fit to be divided from sig
    '''
    ret_pk_guess = False
    if pk_guess is None: 
        ret_pk_guess = True
        pk_guess, _ = plotting.ringsum_click(r,sig,title='Please click on peaks')

    peak_loc = np.zeros(len(pk_guess))
    peak_val = np.zeros(len(pk_guess))
    peak_wts = np.zeros(len(pk_guess))
    for i,pk in enumerate(pk_guess):
        idxs = fitting.determine_fit_range(r, sig, pk, thres=0.1)
        peak_loc[i],peak_val[i] = fitting.find_maximum(r[idxs],sig[idxs],returnval=True)
        peak_wts[i] = 1./(sig_sd[np.abs(peak_loc[i]-r).argmin()])

    p,cov = np.polyfit(peak_loc,peak_val,poly_num,w=peak_wts,cov=True)
    poff = np.polyval(p,r)
    poff_sd = np.sqrt(np.sum(np.diag(cov)))
    if ret_pk_guess:
        return pk_guess,poff,poff_sd
    else:
        return poff, poff_sd

def main(fname, bgfname=None, color='b', binsize=0.1, xguess=None, 
        yguess=None, block_center=False, click_center=True, find_center=True,
        sub_prof=False, plotit=False, write=None):

    bgdata = None
    if fname[-2:].lower() == "h5":
       with h5py.File(fname, 'r') as f:
           data = f.get("2Ddata").value
           bgdata = np.abs(norm(scale=0.05).rvs(data.shape))
    else:
        fname = images.check_nef(fname)
        bgfname = images.check_nef(bgfname)

        print 'loading image...'
        data = images.get_data(fname, color=color)
    npix = 1
    data = ringsum.super_pixelate(data, npix=npix)

    if find_center:
        if click_center:
            xguess,yguess = plotting.center_plot(data)

        x0,y0 = ringsum.locate_center(data, xguess=xguess, yguess=yguess, 
                block_center=block_center, binsize=binsize, plotit=True)

        if plotit:
            fig,ax = plt.subplots(figsize=(10,8))
            plotting.ring_plot(data, fax=(fig,ax))
            ax.axhline(y0,color='b')
            ax.axvline(x0,color='r')
            plt.show()
    else:
        if xguess is None:
            x0 = data.shape[1]/2.
        else:
            x0 = xguess
        if yguess is None:
            y0 = data.shape[0]/2.
        else:
            y0 = yguess

    print 'performing ringsums...'
    r, sig0,sig0_sd = ringsum.ringsum(data,x0,y0, use_weighted=False, quadrants=False) 

    if bgfname is not None or fname[-2:].lower() == "h5":
        print 'removing background...'
        if bgdata is None:
            bgdata = images.get_data(bgfname, color=color)
            bgdata = ringsum.super_pixelate(bgdata, npix=npix)
        _, bg,bg_sd = ringsum.ringsum(bgdata,x0,y0, use_weighted=False)
        sig = sig0 - bg
        sig_sd = np.sqrt(sig0_sd**2+bg_sd**2)
    else:
        sig,sig_sd = sig0,sig0_sd


    if sub_prof:
        print 'subtracting profile fit...'
        pk_guess,p,p_sd = remove_prof(r,sig,sig_sd,pk_guess=None,poly_num=5)
        ### dividing keeps the original offset which is important for gettting the finesse
        sig /= p
        sig_sd = np.sqrt(sig_sd**2+p_sd**2)
        sig_sd /= p

    if fname[-2:].lower() == "h5": 
        dic = {'fname': abspath(fname), 'color': color, 'center': (x0, y0),
                'binsize': binsize, 'r': r, 'sig': sig, 'sig_sd': sig_sd}
    else:
        a = images.get_metadata(fname)
        dic = {'date':a['date'], 'time':a['time'], 'fname':abspath(fname),
                    'color':color, 'center':(x0,y0),
                    'binsize':binsize, 'r':r, 'sig':sig, 'sig_sd': sig_sd}

    if bgfname is not None:
        dic['bg_fname'] = abspath(bgfname)

    if sub_prof:
        dic['pk_guess'] = pk_guess

    print 'done!'

    if write is not None:
        file_io.prep_folder(write)
        file_io.dict_2_h5(join(write,'ringsum.h5'),dic)

    if write is not None or plotit:
        fig,axs = plt.subplots(2,1,figsize=(12,8))

        axs[0].errorbar(r, sig, yerr=sig_sd, fmt='-', errorevery=5, color='r', lw=2, zorder=10, ecolor='b')
        axs[0].axhline(0,color='k',alpha=0.7)
        axs[0].set_title('binsize={0}'.format(binsize))

        axs[1].errorbar(r, sig0, yerr=sig0_sd, fmt='-', errorevery=5, lw=2,label='raw',zorder=10, color='C0', ecolor='C1')
        axs[1].axhline(0,color='k',alpha=0.7)
        if bgfname is not None:
            axs[1].errorbar(r, bg, yerr=bg_sd, fmt='-', errorevery=5, lw=2,label='background',zorder=10, color='C2', ecolor='C3')
        if sub_prof:
            axs[1].fill_between(r, p+p_sd, p-p_sd, label='intensity profile', zorder=10, color='C4',alpha=0.3)
        axs[1].set_xlabel('R (px)')
        axs[1].legend()
        if write:
            file_io.prep_folder(join(write,'plots'))
            plt.savefig(join(write,'plots','ringsum.png'),bbox_inches='tight')
        if plotit:
            plt.show()
        else:
            plt.close()

    fig, ax = plt.subplots()
    ax.plot(r**2, sig, 'C1')
    #ax.plot(r, sig, color='C1')
    ax.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
    #ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
    ax.set_xlabel(r"R${}^2$ (px${}^2$)", fontsize=18)
    #ax.set_xlabel("R (px)", fontsize=18)
    ax.set_ylabel("Counts", fontsize=18)
    ax.tick_params(labelsize=16)
    fig.tight_layout()
    plt.show()
    
    fig, ax = plt.subplots()
    ax.plot(r, sig_sd / sig)
    plt.show()
    return dic

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='stores image ringsum into Data folder')
    parser.add_argument('fname',type=str,help='NEF filename of image you wish to process')
    parser.add_argument('--background','-bg',type=str,default=None,help='NEF filename of\
            background image')
    parser.add_argument('--color', '-c', type=str, default='b', help='r,g,b color to use\
            when ringsumming image: default is b')
    parser.add_argument('--binsize', '-b', type=float, default=0.1, help='binsize for fine\
            ringsum: default is 0.25')
    parser.add_argument('-xy', type=float, nargs='+', default=None, help='x and y guess for\
            the center of image, if not provided the center of the ccd is assumed')
    parser.add_argument('--no_search', action='store_true',help='supresses the center finding\
            algorthim and just uses the provided xy')
    parser.add_argument('--no_click', action='store_true', help='supresses the interactive\
            click plot for getting a center guess')
    parser.add_argument('--block', '-bk', action='store_true', help='sets a 600x600 square\
            block centered on xyguess for center finding')
    parser.add_argument('--sub_prof', '-sp', action='store_true', help='perform a polyfit\
            profile subtraction, launches an interactive plot')
    parser.add_argument('--no_plot', action='store_true', help='supresses plots')
    parser.add_argument('--write', '-w', type=str, default=None, help='saves data and plot to\
            specified folder, default is None which will not write data.')
    args = parser.parse_args()

    plotit = not args.no_plot
    click_center = not args.no_click
    find_center = not args.no_search

    if args.xy is None:
        xguess = None
        yguess = None
    else:
        xguess, yguess = args.xy

    _ = main(args.fname, bgfname=args.background, color=args.color, binsize=args.binsize,
            block_center=args.block, sub_prof=args.sub_prof, 
            write=args.write, plotit=plotit, click_center=click_center, xguess=xguess,
            yguess=yguess, find_center=find_center)

