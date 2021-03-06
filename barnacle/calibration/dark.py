# -*- coding: utf-8 -*-
"""
This script generates the average dark used in the signal processing of
datacube.
``dark`` means background noise in the detector.
It is measured when no light is collected by the pixels.
It relies on the library :doc:`glint_classes` to work.

The products are:
    * average dark frame
    * average dark per channel

Some monitoring data can be created:
    * histogram of dark on the whole frame on the whole datacube (hdf5 file)
    * optimal parameters from a Gaussian fitting of this histogram (hdf5 file)
    * histogram of the dark per channel on the whole datacube (hdf5 file)
    * Evolution of the dark in different areas of the frame along the
      frame-axis of the datacube (non-saved plot)

This script is used in 3 steps.

First step: specify the following settings:
    * :save: *(boolean)* -- ``True`` for saving products and monitoring data,
              ``False`` otherwise
    * :monitor: *(boolean)* --  ``True`` for creating histogram of
                the background noise and plotting them
    * :nb_files: *(2-tuple of int)* -- set the bounds between which
                 the dark files are selected.
                 ``None`` is equivalent to 0 if it is the lower bound or -1
                 included or it is the upper one.
    * :edges: *(tuple)* -- minimal left-edge and maximal right-edge of
              the histograms.

Second step: specify the paths to load data and save outputs:
    * :datafolder: *(string)* -- folder containing the datacube to use.
    * :dark_list: *(list )* -- list of files in **datafolder** to open.

Third step: call function ``get_average_dark``.

Example available in ``examples/run_dark.py``.
"""

import os
import h5py
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit
from barnacle.glint_functions import gaussian_curve, get_channel_positions
import barnacle.glint_classes as glint_classes

NB_TRACKS = 16


def save_histo_dark(path, dic_data, mode='channel'):
    """
    Save the histogram of the dark into a HDF5 file.

    :param path: path of the file to save. Must contain the name of
                   the file+extension.
    :type path: string
    :param dic_data: dictionary of data to save
    :type dic_data: dict
    :param mode: if ``channel``, the information per channel is saved
                instead of the information got from the whole frame,
                defaults to 'channel'.
    :type mode: string, optional
    :return: No return
    :rtype: Nothing-type

    """
    # Check if saved file exist
    if os.path.exists(path):
        opening_mode = 'w'  # Overwright the whole existing file.
    else:
        opening_mode = 'a'  # Create a new file at "path"

    if mode == 'channel':
        track_id = {'p1': 15, 'p2': 13, 'p3': 2, 'p4': 0,
                    'null1': 11, 'null2': 3, 'null3': 1, 'null4': 6,
                    'null5': 5, 'null6': 8, 'antinull1': 9, 'antinull2': 12,
                    'antinull3': 14, 'antinull4': 4, 'antinull5': 7,
                    'antinull6': 10}

        with h5py.File(path, opening_mode) as f:
            for key, value in track_id.items():
                f.create_dataset(key, data=dic_data[value])
    else:
        with h5py.File(path, opening_mode) as f:
            f.create_dataset('histogram', data=dic_data)


def get_histogram(data, bins):
    """
    Return the histogram of ``data`` according to the ``bins``.

    :param data: data used to create the histogram,
                 if dim>1, it is flattened
    :type data: array
    :param bins: left bin edges of the histogram.
        The last element is the right edge of the last bin.
    :type bins: array
    :return: Non-normalized histogram.
    :rtype: array

    """
    if len(data.shape) != 1:
        data = np.ravel(data)

    histo = np.histogram(np.ravel(data), bins=bins)[0]
    return histo


def get_average_dark(data_path, output_path, nb_files, save, monitor, edges, keyword):
    """
    Calculate the average dark for the whole frame and channel by channel.

    :param data_path: list of dark files to process.
    :type data_path: list
    :param output_path: path where to saved the outputs.
    :type output_path: string
    :param nb_files: indexes of the first file and the last one (excluded)
                        to process.
    :type nb_files: tuple
    :param save: if ``True``, save the outputs of the function.
    :type save: bool
    :param monitor: if ``True``, plot histograms about the dark.
    :type monitor: bool
    :param edges: minimal and maximal values of the histograms
    :type edges: tuple
    :param keyword: keyword to select the dark files to process
    :type output_path: string
    :return: the average dark on the whole frame and per channel.
    :rtype: tuple

    """
    edge_min, edge_max = edges
    dark_list = [data_path+f for f in os.listdir(data_path)
                 if keyword in f and not '.txt' in f][nb_files[0]:nb_files[1]]

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    ''' Define bounds of each track '''
    channel_pos, sep = get_channel_positions(NB_TRACKS)

    ''' Computing average dark '''
    super_dark = np.zeros((344, 96))
    super_dark_channel = np.zeros((96, 16, 20))
    nb_img = 0.

    for f in dark_list[:]:
        print("Process of : %s (%d / %d)" %
              (f, dark_list.index(f)+1, len(dark_list)))
        dark = glint_classes.Null(f)

        super_dark = super_dark + dark.data.sum(axis=0)
        nb_img = nb_img + dark.nbimg

        spatial_axis = np.arange(dark.data.shape[0])
        dark.getChannels(channel_pos, sep, spatial_axis)

        super_dark_channel = super_dark_channel + dark.slices.sum(axis=0)

        if monitor:
            try:
                avg_dark = np.vstack((avg_dark, np.reshape(
                    dark.data.mean(axis=(1, 2)), (-1, 1))))
            except NameError:
                print('except')
                avg_dark = np.reshape(dark.data.mean(axis=(1, 2)), (-1, 1))

    if nb_img != 0.:
        super_dark /= nb_img
        super_dark_channel = super_dark_channel / nb_img
        if save:
            np.save(output_path+'superdark', super_dark)
            np.save(output_path+'superdarkchannel', super_dark_channel)

    if monitor:
        params, hist_channels, hist_global = \
            check_dark(dark_list, avg_dark, channel_pos, sep, spatial_axis,
                       edge_min, edge_max, super_dark_channel, save,
                       output_path)

    if monitor:
        return super_dark, super_dark_channel,\
            params, hist_channels, hist_global
    else:
        return super_dark, super_dark_channel


def check_dark(dark_list, avg_dark, channel_pos, sep, spatial_axis, edge_min,
               edge_max, super_dark_channel, save, output_path):
    """
    Plot histograms and timelapse to control the dark.

    One can detect drifts, bad pixels, electronic anomalies, etc.

    :param dark_list: list of the dark files to process.
    :type dark_list: list
    :param avg_dark: average dark of the whole frame.
    :type avg_dark: 2D-array
    :param channel_pos: position of the 16 channels.
    :type channel_pos: list-like
    :param sep: gap between the channels, in pixel.
    :type sep: float
    :param spatial_axis: y-axis of the frame.
    :type spatial_axis: array-like
    :param edge_min: minimal value of the histograms.
    :type edge_min: float
    :param edge_max: maximal values of the histograms.
    :type edge_max: float
    :param super_dark_channel: average dark per channel.
    :type super_dark_channel: array
    :param save: if ``True``, save the outputs of the functions.
    :type save: bool
    :return: Fitted parameters, the histograms per channel and the histogram
                of the whole frame.
    :rtype: tuple

    """
    bin_hist, step = np.linspace(
        edge_min-0.5, edge_max+0.5, edge_max-edge_min+1, retstep=True)
    bin_hist_cent = bin_hist[:-1] + step/2
    hist_slices = []
    list_hist = []

    for f in dark_list:
        print("Histogram of : %s (%d / %d)" %
              (f, dark_list.index(f)+1, len(dark_list)))
        dark = glint_classes.Null(f)
        spatial_axis = np.arange(dark.data.shape[0])
        hist = np.histogram(np.ravel(
            dark.data - dark.data.mean(axis=(1, 2))[:, None, None]),
            bins=bin_hist)
        list_hist.append(hist[0])

        dark.getChannels(channel_pos, sep, spatial_axis)
        dark.slices = dark.slices - super_dark_channel

        try:
            dark_current = np.vstack(
                (dark_current, dark.slices.mean(axis=(1, 3))))
            dk56 = np.vstack(
                (dk56, np.reshape(dark.slices[:, 56, 15, :].mean(axis=-1),
                                  (-1, 1))))
            dk56bis = np.vstack(
                (dk56, np.reshape(dark.slices[:, 56, 15, 10].mean(axis=-1),
                                  (-1, 1))))
        except NameError:
            print('except 2')
            dark_current = dark.slices.mean(axis=(1, 3))
            dk56 = np.reshape(
                dark.slices[:, 56, 15, :].mean(axis=-1), (-1, 1))
            dk56bis = np.reshape(
                dark.slices[:, 56, 15, 10].mean(axis=-1), (-1, 1))

        histo_per_file = []
        for k in range(16):
            histo_per_file.append(get_histogram(
                np.ravel(dark.slices[:, :, k, :]), bin_hist))
        hist_slices.append(histo_per_file)

    list_hist = np.array(list_hist)
    hist_slices = np.array(hist_slices)
    super_hist = np.sum(hist_slices, axis=0)
    super_hist = super_hist / np.sum(super_hist, axis=1)[:, None]

    list_hist = np.sum(list_hist, axis=0)
    list_hist = list_hist / np.sum(list_hist)

    params = []
    for i in range(16):
        popt, pcov = curve_fit(gaussian_curve, bin_hist_cent,
                               super_hist[i],
                               p0=[max(super_hist[i]), 0., 50])
        params.append(popt)
    params = np.array(params)

    hist_to_save = np.empty((super_hist.shape[0], super_hist.shape[1], 2))
    hist_to_save[:, :, 0] = super_hist
    hist_to_save[:, :, 1] = bin_hist[:-1]

    if save:
        save_histo_dark(output_path+'hist_dk_params.hdf5', params)
        save_histo_dark(output_path+'hist_dk_slices.hdf5', hist_to_save)
        save_histo_dark(output_path+'hist_dk.hdf5',
                        np.array([list_hist, bin_hist[:-1]]), 'global')

    popt, pcov = curve_fit(gaussian_curve, bin_hist_cent, list_hist, p0=[
                           max(list_hist), 0, 50])
    f = plt.figure(figsize=(19.20, 10.80))
    ax = f.add_subplot(111)
    plt.plot(bin_hist_cent, list_hist, lw=5)
    plt.plot(bin_hist_cent, gaussian_curve(
        bin_hist_cent, *popt), lw=4, alpha=0.8)
    plt.grid()
    plt.xlabel('Dark current', size=40)
    plt.ylabel('Counts (normalised)', size=40)
    plt.xticks(size=35)
    plt.yticks(size=35)
    txt = r'$\mu = %.3f$' % (popt[1]) + '\n' + \
        r'$\sigma = %.3f$' % (popt[2])
    plt.text(0.05, 0.6, txt, va='center', fontsize=30,
             transform=ax.transAxes,
             bbox=dict(boxstyle="square", facecolor='white'))
    if save:
        plt.savefig(output_path+'histogram_dark_fullframe.png')

    plt.figure(figsize=(19.20, 10.80))
    for i in range(16):
        lab = r'$\mu = $%.3f' % params[i, 1] + \
            '\n'+r'$\sigma = $%.3f' % params[i, 2]
        plt.subplot(4, 4, i+1)
        plt.plot(bin_hist_cent, super_hist[i])
        plt.plot(bin_hist_cent, gaussian_curve(
            bin_hist_cent, *params[i]), label=lab)
        plt.grid()
        plt.xlabel('Dark current (ADU)')
        plt.ylabel('Count')
        plt.legend(loc='upper left')
    #    plt.xticks(size=36);plt.yticks(size=36)
    plt.suptitle('Histogram of the background noise')
    if save:
        plt.savefig(output_path+'histogram_dark.png')

    plt.figure(figsize=(19.20, 10.80))
    for i in range(16):
        lab = r'$\mu = $%.3f' % params[i, 1] + \
            '\n'+r'$\sigma = $%.3f' % params[i, 2]
        plt.subplot(4, 4, i+1)
        plt.semilogy(bin_hist_cent, super_hist[i])
        plt.semilogy(bin_hist_cent, gaussian_curve(
            bin_hist_cent, *params[i]), label=lab)
        plt.grid()
        plt.xlabel('Dark current (ADU)')
        plt.ylabel('Count')
        plt.legend(loc='upper left')
        plt.ylim(1e-8, 10)
    #    plt.xlim(-1000,1000)
    #    plt.xticks(size=36);plt.yticks(size=36)
    plt.suptitle('Histogram of the background noise')
    if save:
        plt.savefig(output_path+'histogram_dark_logscale.png')

    ''' Inspecting non-uniformities '''
    hist_dk56, bin_dk56 = np.histogram(dk56, bins=int(len(dk56)**0.5))
    bin_dk56_cent = bin_dk56[:-1] + np.diff(bin_dk56)/2
    hist_dk56 = hist_dk56 / np.sum(hist_dk56)

    popt, pcov = curve_fit(gaussian_curve, bin_dk56_cent, hist_dk56,
                           p0=[max(hist_dk56), dk56.mean(),
                               dk56.std()])
    f = plt.figure(figsize=(19.20, 10.80))
    ax = f.add_subplot(111)
    plt.title(
        'Histogram of dark current of P1 at 56th column of pixel',
        size=40)
    plt.semilogy(bin_dk56_cent, hist_dk56, lw=5, label='Histogram')
    plt.semilogy(bin_dk56_cent, gaussian_curve(
        bin_dk56_cent, *popt), lw=3, alpha=0.8, label='Gaussian fit')
    plt.grid()
    plt.xlabel('Dark current', size=40)
    plt.ylabel('Counts (normalised)', size=40)
    plt.xticks(size=40)
    plt.yticks(size=40)
    txt = r'$\mu = %.3f$' % (popt[1]) + \
        '\n' + r'$\sigma = %.3f$' % (popt[2])
    plt.text(0.5, 0.1, txt, va='center', fontsize=30,
             transform=ax.transAxes,
             bbox=dict(boxstyle="square", facecolor='white'))

    hist_dk56bis, bin_dk56bis = np.histogram(
        dk56bis, bins=int(len(dk56bis)**0.5))
    bin_dk56bis_cent = bin_dk56bis[:-1] + np.diff(bin_dk56bis)/2
    hist_dk56bis = hist_dk56bis / np.sum(hist_dk56bis)

    popt, pcov = curve_fit(gaussian_curve, bin_dk56bis_cent,
                           hist_dk56bis,
                           p0=[max(hist_dk56bis), dk56bis.mean(),
                               dk56bis.std()])
    f = plt.figure(figsize=(19.20, 10.80))
    ax = f.add_subplot(111)
    plt.title(
        'Histogram of dark current of center of P1 at 56th '
        'column of pixel', size=40)
    plt.semilogy(bin_dk56bis_cent, hist_dk56bis,
                 lw=5, label='Histogram')
    plt.semilogy(bin_dk56bis_cent, gaussian_curve(
        bin_dk56bis_cent, *popt), lw=3, alpha=0.8,
        label='Gaussian fit')
    plt.grid()
    plt.xlabel('Dark current', size=40)
    plt.ylabel('Count (normalised)', size=40)
    plt.xticks(size=40)
    plt.yticks(size=40)
    txt = r'$\mu = %.3f$' % (popt[1]) + \
        '\n' + r'$\sigma = %.3f$' % (popt[2])
    plt.text(0.5, 0.1, txt, va='center', fontsize=30,
             transform=ax.transAxes, bbox=dict(boxstyle="square",
                                               facecolor='white'))

    plt.figure(figsize=(19.20, 10.80))
    for i in range(16):
        time = np.arange(dark_current.shape[0])
        shape = dark_current.shape
        binning = 10
        new_shape = int(shape[0]//binning*binning)
        time_binned = np.reshape(
            time[:new_shape], (int(new_shape/binning), binning))
        time_binned = np.mean(time_binned, axis=1)
        dark_current_binned = np.reshape(
            dark_current[:new_shape, i], (int(new_shape/binning),
                                          binning))
        dark_current_binned = np.mean(dark_current_binned, axis=1)
        print(dark_current_binned.mean(), dark_current_binned.std())
        popt = np.polyfit(time_binned, dark_current_binned, 1)
        p = np.poly1d(popt)
        plt.subplot(4, 4, i+1)
        plt.plot(time[::500], dark_current[::500, i],
                 alpha=0.5, label='Data (subsampled)')
        plt.plot(time_binned, dark_current_binned,
                 label='Binned data (%s)' % binning)
        plt.plot(time[::500], p(time[::500]), label='Fit')
        plt.grid()
        plt.ylim(-4.5, 4.5)
        plt.title('Track %s (Drift = %.3E/frame)' % (i+1, popt[0]))
        plt.xlabel('Frame')
        plt.ylabel('Avg dark current')
        if i == 0:
            plt.legend(loc='best')
    plt.tight_layout()
    if save:
        plt.savefig(output_path+'avg_time_lapse.png')

    plt.figure(figsize=(19.20, 10.80))
    plt.plot(np.arange(dk56.size)[::1], dk56[::1])
    plt.grid()
    plt.xlabel('Frame/100', size=30)
    plt.ylabel('Avg amplitude', size=30)
    plt.xticks(size=30)
    plt.yticks(size=30)
    plt.title('Avg dark current in P1 at 56th column of pixels',
              size=35)

    plt.figure(figsize=(19.20, 10.80))
    plt.plot(np.arange(dk56bis.size)[::1], dk56bis[::1])
    plt.grid()
    plt.xlabel('Frame/100', size=30)
    plt.ylabel('Avg amplitude', size=30)
    plt.xticks(size=30)
    plt.yticks(size=30)
    plt.title(
        'Dark current at center of P1 at 56th column of pixels',
        size=35)

    plt.figure(figsize=(19.20, 10.80))
    avg_dark = np.reshape(avg_dark, (-1,))
    time = np.arange(avg_dark.size)
    shape = avg_dark.shape
    binning = 10
    new_shape = int(shape[0]//binning*binning)
    time_binned = np.reshape(time[:new_shape], (-1, binning))
    avg_dark_binned = np.reshape(avg_dark[:new_shape], (-1, binning))
    time_binned = np.mean(time_binned, axis=1)
    avg_dark_binned = np.mean(avg_dark_binned, axis=1)
    popt = np.polyfit(time_binned, avg_dark_binned, 1)
    p = np.poly1d(popt)
    plt.plot(time[::1], avg_dark[::1], lw=3, alpha=0.5, label='Data')
    plt.plot(time_binned, avg_dark_binned, lw=3,
             label='Binned data (%s)' % binning)
    plt.plot(time[::1], p(time[::1]), lw=2, alpha=0.8, label='Fit')
    plt.grid()
    plt.xlabel('Frame', size=30)
    plt.ylabel('Avg dark current', size=30)
    plt.xticks(size=30)
    plt.yticks(size=30)
    plt.title(
        'Average dark current on whole frame'
        '(Drift = %.3E/frame)' % popt[0], size=35)
    plt.legend(loc='best')
    if save:
        plt.savefig(output_path+'avg_dark_fullframe.png')

    return params, hist_to_save, np.array([list_hist, bin_hist[:-1]])
