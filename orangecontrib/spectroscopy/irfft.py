from enum import IntEnum

import numpy as np
import scipy.signal


class ApodFunc(IntEnum):
    """
    Implemented apodization functions in apodize
    """
    BOXCAR = 0
    BLACKMAN_HARRIS_3 = 1
    BLACKMAN_HARRIS_4 = 2
    BLACKMAN_NUTTALL = 3


class PhaseCorrection(IntEnum):
    """
    Implemented phase correction methods
    """
    MERTZ = 0
    MERTZSIGNED = 1
    STORED = 2
    NONE = 3


class PeakSearch(IntEnum):
    """
    Implemented peak search functions
    """
    MAXIMUM = 0
    MINIMUM = 1
    ABSOLUTE = 2


def find_zpd(ifg, peak_search):
    """
    Find the zero path difference (zpd) position.

    Args:
        ifg (np.array): 1D array with a single interferogram
        peak_search (IntEnum): One of peak search functions:
            <PeakSearch.MAXIMUM: 0>         : Maximum value
            <PeakSearch.MINIMUM: 1>         : Minumum value
            <PeakSearch.ABSOLUTE: 2>        : Absolute largest value

    Returns:
        zpd: The index of zpd in ifg array.
    """
    if peak_search == PeakSearch.MAXIMUM:
        return ifg.argmax()
    elif peak_search == PeakSearch.MINIMUM:
        return ifg.argmin()
    elif peak_search == PeakSearch.ABSOLUTE:
        return ifg.argmin() if abs(ifg.min()) > abs(ifg.max()) else ifg.argmax()
    else:
        raise NotImplementedError

def apodize(ifg, zpd, apod_func):
    """
    Perform apodization of asymmetric interferogram using selected apodization
    function

    Args:
        ifg (np.array): interferogram array (1D or 2D row-wise)
        zpd (int): Index of the Zero Phase Difference (centerburst)
        apod_func (IntEnum): One of apodization function options:
                <ApodFunc.BOXCAR: 0>            : Boxcar apodization
                <ApodFunc.BLACKMAN_HARRIS_3: 1> : Blackman-Harris (3-term)
                <ApodFunc.BLACKMAN_HARRIS_4: 2> : Blackman-Harris (4-term)
                <ApodFunc.BLACKMAN_NUTTALL: 3>  : Blackman-Nuttall (Eric Peach implementation)

    Returns:
        ifg_apod (np.array): apodized interferogram(s)
    """

    # Calculate negative and positive wing size
    # correcting zpd from 0-based index
    ifg_N = ifg.shape[-1]
    wing_n = zpd + 1
    wing_p = ifg_N - (zpd + 1)

    if apod_func == ApodFunc.BOXCAR:
        # Boxcar apodization AKA as-collected
        return ifg

    elif apod_func == ApodFunc.BLACKMAN_HARRIS_3:
        # Blackman-Harris (3-term)
        # Reference: W. Herres and J. Gronholz, Bruker
        #           "Understanding FT-IR Data Processing"
        A0 = 0.42323
        A1 = 0.49755
        A2 = 0.07922
        A3 = 0.0
        n_n = np.arange(wing_n)
        n_p = np.arange(wing_p)
        Bs_n = A0\
            + A1 * np.cos(np.pi*n_n/wing_n)\
            + A2 * np.cos(np.pi*2*n_n/wing_n)\
            + A3 * np.cos(np.pi*3*n_n/wing_n)
        Bs_p = A0\
            + A1 * np.cos(np.pi*n_p/wing_p)\
            + A2 * np.cos(np.pi*2*n_p/wing_p)\
            + A3 * np.cos(np.pi*3*n_p/wing_p)
        Bs = np.hstack((Bs_n[::-1], Bs_p))

    elif apod_func == ApodFunc.BLACKMAN_HARRIS_4:
        # Blackman-Harris (4-term)
        # Reference: W. Herres and J. Gronholz, Bruker
        #           "Understanding FT-IR Data Processing"
        A0 = 0.35875
        A1 = 0.48829
        A2 = 0.14128
        A3 = 0.01168
        n_n = np.arange(wing_n)
        n_p = np.arange(wing_p)
        Bs_n = A0\
            + A1 * np.cos(np.pi*n_n/wing_n)\
            + A2 * np.cos(np.pi*2*n_n/wing_n)\
            + A3 * np.cos(np.pi*3*n_n/wing_n)
        Bs_p = A0\
            + A1 * np.cos(np.pi*n_p/wing_p)\
            + A2 * np.cos(np.pi*2*n_p/wing_p)\
            + A3 * np.cos(np.pi*3*n_p/wing_p)
        Bs = np.hstack((Bs_n[::-1], Bs_p))

    elif apod_func == ApodFunc.BLACKMAN_NUTTALL:
        # Blackman-Nuttall (Eric Peach)
        # TODO I think this has silent problems with asymmetric interferograms
        delta = np.min([wing_n, wing_p])

        # Create Blackman Nuttall Window according to the formula given by Wolfram.
        xs = np.arange(ifg_N)
        Bs = np.zeros(ifg_N)
        Bs = 0.3635819\
            - 0.4891775 * np.cos(2*np.pi*xs/(2*delta - 1))\
            + 0.1365995 * np.cos(4*np.pi*xs/(2*delta - 1))\
            - 0.0106411 * np.cos(6*np.pi*xs/(2*delta - 1))

    # Apodize the sampled Interferogram
    try:
        ifg_apod = ifg * Bs
    except ValueError as e:
        raise ValueError("Apodization function size mismatch: %s" % e)

    return ifg_apod

def _zero_fill_size(ifg_N, zff):
    # Calculate desired array size
    Nzff = ifg_N * zff
    # Calculate final size to next power of two for DFT efficiency
    return int(np.exp2(np.ceil(np.log2(Nzff))))

def _zero_fill_pad(ifg, zerofill):
    zeroshape = (ifg.shape[0], zerofill) if ifg.ndim == 2 else zerofill
    return np.hstack((ifg, np.zeros(zeroshape, dtype=ifg.dtype)))

def zero_fill(ifg, zff):
    """
    Zero-fill interferogram to DFT-efficient power of two.
    Assymetric to prevent zpd from changing index.

    Args:
        ifg (np.array): interferogram array (1D or 2D row-wise)
        zff (int): Zero-filling factor

    Returns:
        np.array: ifg with appended zero fill
    """
    ifg_N = ifg.shape[-1]
    # Calculate zero-fill to next power of two for DFT efficiency
    zero_fill = _zero_fill_size(ifg_N, zff) - ifg_N
    # Pad array
    return _zero_fill_pad(ifg, zero_fill)

def find_peak_zero_fill(ifg, type_peak, number_of_points):
    if type_peak == 0: # MAXIMUM = 0
        peak = max(ifg.real)
    elif type_peak == 1: # MINIMUM = 1
        peak = min(ifg.real)
    else: #ABSOLUTE = 2
        peak = max(abs(ifg.real))

    if type_peak == 2:
        index, = np.where(abs(ifg.real) == peak)
    else:
        index, = np.where(ifg.real == peak)

    delta_center = int((number_of_points / 2 - index))
    if delta_center < 0:
        zeros = np.zeros((abs(delta_center)))
        ifg = np.delete(ifg, np.s_[:abs(delta_center)])
        ifg = np.concatenate((ifg, zeros))
    elif delta_center > 0:
        zeros = np.zeros((abs(delta_center)))
        ifg = np.delete(ifg, np.s_[-abs(delta_center):])
        ifg = np.concatenate((zeros, ifg))

    return ifg


class IRFFT():
    """
    Calculate FFT of a single interferogram sweep.

    Based on mertz module by Eric Peach, 2014
    """
    # Calculated attributes
    zpd = None
    wavenumbers = None
    spectrum = None
    phase = None


    def __init__(self, dx,
                 apod_func=ApodFunc.BLACKMAN_HARRIS_3, zff=2,
                 phase_res=None, phase_corr=PhaseCorrection.MERTZ,
                 peak_search=PeakSearch.MAXIMUM,
                ):
        self.dx = dx
        self.apod_func = apod_func
        self.zff = zff
        self.phase_res = phase_res
        self.phase_corr = phase_corr
        self.peak_search = peak_search

    def __call__(self, ifg, zpd=None, phase=None):
        if ifg.ndim != 1:
            raise ValueError("ifg must be 1D array")
        # Stored phase
        self.phase = phase
        # Stored ZPD
        if zpd is not None:
            self.zpd = zpd
        else:
            self.zpd = find_zpd(ifg, self.peak_search)

        # Subtract DC value from interferogram
        ifg = ifg - ifg.mean()

        # Calculate phase on interferogram of specified size 2*L
        L = self.phase_ifg_size(ifg.shape[0])
        if L == 0: # Use full ifg for phase
            ifg = apodize(ifg, self.zpd, self.apod_func)
            ifg = zero_fill(ifg, self.zff)
            # Rotate the Complete IFG so that the centerburst is at edges.
            ifg = np.hstack((ifg[self.zpd:], ifg[0:self.zpd]))
            Nzff = ifg.shape[0]
            # Take FFT of Rotated Complete Graph
            ifg = np.fft.rfft(ifg)
            self.compute_phase(ifg)
        else:
            # Select phase interferogram as copy
            # Note that L is now the zpd index
            Ixs = ifg[self.zpd - L : self.zpd + L].copy()
            ifg = apodize(ifg, self.zpd, self.apod_func)
            ifg = zero_fill(ifg, self.zff)
            ifg = np.hstack((ifg[self.zpd:], ifg[0:self.zpd]))
            Nzff = ifg.shape[0]

            Ixs = apodize(Ixs, L, self.apod_func)
            # Zero-fill Ixs to same size as ifg (instead of interpolating later)
            Ixs = _zero_fill_pad(Ixs, Nzff - Ixs.shape[0])
            Ixs = np.hstack((Ixs[L:], Ixs[0:L]))

            ifg = np.fft.rfft(ifg)
            Ixs = np.fft.rfft(Ixs)
            self.compute_phase(Ixs)

        self.wavenumbers = np.fft.rfftfreq(Nzff, self.dx)

        if self.phase_corr == PhaseCorrection.NONE:
            self.spectrum = ifg.real
            self.phase = ifg.imag
        else:
            try:
                self.spectrum = np.cos(self.phase) * ifg.real + np.sin(self.phase) * ifg.imag
            except ValueError as e:
                raise ValueError("Incompatible phase: {}".format(e))

        return self.spectrum, self.phase, self.wavenumbers

    def phase_ifg_size(self, ifg_N):
        # Determine largest possible double-sided interferogram
        delta = np.min([self.zpd, ifg_N - 1 - self.zpd])
        # Reduce to desired resolution if specified
        # TODO make a single function to implement setting output resolution
        if self.phase_res is not None:
            # TODO check this
            L = int(1 / (self.dx * self.phase_res)) - 1
            if L < delta:
                delta = L

        return delta

    def compute_phase(self, ifg_sub_fft):
        if self.phase_corr == PhaseCorrection.NONE:
            return
        elif self.phase_corr == PhaseCorrection.STORED:
            if self.phase is None:
                raise ValueError("No stored phase provided.")
            return
        elif self.phase_corr == PhaseCorrection.MERTZ:
            self.phase = np.arctan2(ifg_sub_fft.imag, ifg_sub_fft.real)
        elif self.phase_corr == PhaseCorrection.MERTZSIGNED:
            self.phase = np.arctan(ifg_sub_fft.imag/ifg_sub_fft.real)
        else:
            raise ValueError("Invalid PhaseCorrection: {}".format(self.phase_corr))


class MultiIRFFT(IRFFT):

    def __call__(self, ifg, zpd=None, phase=None):
        if ifg.ndim != 2:
            raise ValueError("ifg must be 2D array of row-wise interferograms")
        # TODO does stored phase work / make sense here?
        self.phase = phase
        try:
            self.zpd = int(zpd)
        except TypeError:
            raise TypeError("zpd must be specified as a single value valid for all interferograms")

        # Subtract DC value from interferogram
        ifg = ifg - ifg.mean(axis=1, keepdims=True)

        # Calculate phase on interferogram of specified size 2*L
        L = self.phase_ifg_size(ifg.shape[1])
        if L == 0: # Use full ifg for phase #TODO multi is this code tested
            ifg = apodize(ifg, self.zpd, self.apod_func)
            ifg = zero_fill(ifg, self.zff)
            # Rotate the Complete IFG so that the centerburst is at edges.
            ifg = np.hstack((ifg[self.zpd:], ifg[0:self.zpd]))
            Nzff = ifg.shape[0]
            # Take FFT of Rotated Complete Graph
            ifg = np.fft.rfft(ifg)
            self.compute_phase(ifg)
        else:
            # Select phase interferogram as copy
            # Note that L is now the zpd index
            Ixs = ifg[:, self.zpd - L : self.zpd + L].copy()
            ifg = apodize(ifg, self.zpd, self.apod_func)
            ifg = zero_fill(ifg, self.zff)
            ifg = np.hstack((ifg[:, self.zpd:], ifg[:, 0:self.zpd]))
            Nzff = ifg.shape[1]

            Ixs = apodize(Ixs, L, self.apod_func)
            # Zero-fill Ixs to same size as ifg (instead of interpolating later)
            Ixs = _zero_fill_pad(Ixs, Nzff - Ixs.shape[1])
            Ixs = np.hstack((Ixs[:, L:], Ixs[:, 0:L]))

            ifg = np.fft.rfft(ifg)
            Ixs = np.fft.rfft(Ixs)
            self.compute_phase(Ixs)

        self.wavenumbers = np.fft.rfftfreq(Nzff, self.dx)

        if self.phase_corr == PhaseCorrection.NONE:
            self.spectrum = ifg.real
            self.phase = ifg.imag
        else:
            try:
                self.spectrum = np.cos(self.phase) * ifg.real + np.sin(self.phase) * ifg.imag
            except ValueError as e:
                raise ValueError("Incompatible phase: {}".format(e))

        return self.spectrum, self.phase, self.wavenumbers


class ComplexFFT(IRFFT):

    def __call__(self, ifg, zpd=None, phase=None):
        number_of_points = len(ifg)
        Nzff = self.zff*number_of_points

        ifg -= np.mean(ifg)
        ifg = find_peak_zero_fill(ifg, type_peak=self.peak_search,
                                  number_of_points=number_of_points)

        '''Options: boxcar, triang, blackman, hamming, hann, bartlett,
        flattop, parzen, bohman, blackmanharris, nuttall, barthann '''
        choosed_window = {
            '0': 'boxcar', # Boxcar (None)
            '1': 'blackman', # Blackman-Harris (3-term)
            '2': 'blackmanharris', # Blackman-Harris (4-term)
            '3': 'nuttall', # Blackman Nuttall (EP)
        }

        window = scipy.signal.get_window(choosed_window[str(self.apod_func)],
                                         number_of_points, fftbins=True)
        ifg = ifg * window
        ifg = np.fft.fft(ifg, n=Nzff)
        magnitude = np.abs(ifg)
        angle = np.angle(ifg)
        self.wavenumbers = np.fft.rfftfreq(Nzff, self.dx)
        self.spectrum = magnitude[:len(self.wavenumbers)]
        self.phase = angle[:len(self.wavenumbers)]

        return self.spectrum, self.phase, self.wavenumbers
