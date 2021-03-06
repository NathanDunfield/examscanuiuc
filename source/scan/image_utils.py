
'''
Scanned pages are upside-down PDFs.

Convention: We work convert everything to 8-bit grayscale images.
'''

import glob, os, re, subprocess, tempfile, shutil
from math import pi
import warnings
import numpy as np
import scipy.misc
import skimage, skimage.filters, skimage.transform, skimage.morphology

def images_from_pdf(file_path, rotate=True, extra_flags=None):
    directory = tempfile.mkdtemp()
    command = ['pdfimages', '-tiff']
    if extra_flags is not None:
        command += extra_flags
    command += [file_path, os.path.join(directory, 'im')]
    subprocess.call(command)
    images = [scipy.misc.imread(file) for file in glob.glob(os.path.join(directory, 'im*.tif'))]
    if rotate:
        images = [image[::-1, ::-1] for image in images]
    shutil.rmtree(directory)
    return images

def image_from_pdf(file_path, rotate=True):
    images = images_from_pdf(file_path, rotate)
    assert(len(images) == 1)
    return images[0]

def first_image_from_pdf(file_path, rotate=True):
    images = images_from_pdf(file_path, rotate, extra_flags=['-l', '1'])
    assert(len(images) == 1)
    return images[0]

def smooth_image(image, sigma=2):
    ''' Return smoothed image without changing the overall resolution. '''

    if sigma == 0:
        return image.copy()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        image = skimage.filters.gaussian(image, sigma)
        image[image > 1] = 1
        image = skimage.img_as_ubyte(image)
        return image

def smooth_image_with_threshold(image, sigma=1):
    ''' Return smoothed image with threshold sharpening without changing the overall resolution. '''
    image = smooth_image(image, sigma)
    chopped = skimage.filters.threshold_otsu(image) < image
    return skimage.img_as_ubyte(chopped)

def square_dilation(image, size=2):
    ''' Apply morphological dilation to enlarge white regions using a square selem '''
    selem = skimage.morphology.square(size)
    image = skimage.morphology.dilation(image, selem)
    return skimage.img_as_ubyte(image)

def image_fraction(image, xys):
    ''' Return a subimage where x & y are fractions of the width & height. '''
    x1, y1, x2, y2 = xys
    x1, x2 = sorted([x1, x2])
    y1, y2 = sorted([y1, y2])
    h, w = image.shape
    return image[int(y1 * h) : int(y2 * h), int(x1 * w) : int(x2 * w)]

def make_longest_almost_vertical_exact(image, dtheta=0.17, samples=100):
    ''' Rotate the given image so that the longest vertical line is actually vertical. '''
    angles = np.linspace(-dtheta, dtheta, samples)
    data = skimage.transform.hough_line(image, angles)
    _, angles, _ = skimage.transform.hough_line_peaks(*data, num_peaks=1)
    return skimage.transform.rotate(image, angles[0] * 180 / pi)  # Rotate needs degrees!

def make_longest_almost_horizontal_exact(image, dtheta=0.17, samples=100):
    return make_longest_almost_vertical_exact(image.T, dtheta, samples).T

def black_density(image):
    # The convention here is that 0 is white and 1 is black.

    return float(image.sum()) / image.size

def extract_box(image, sides='NESW', align='horizontal', percent=0.5):
    ''' Slice sides off of the given image. '''

    sides = set(sides)
    image = skimage.img_as_float(image)
    # Convention is 1 is black
    if black_density(image) > 0.5: image = 1 - image

    # Rotate a little so horizontal and vertical lines are exactly such.
    if align == 'horizontal':
        image = make_longest_almost_horizontal_exact(image)
    else:  # align == 'vertical'.
        image = make_longest_almost_vertical_exact(image)

    smoothed = skimage.morphology.erosion(image)  # This seems even better than smoothing.
    height, width = smoothed.shape
    # Cut off a given percentage from the top, bottom, left and right
    # to analyse.
    l, r = smoothed[ : , :int(percent*width)], smoothed[ : , int(-percent*width): ]
    t, b = smoothed[ :int(percent*height), : ], smoothed[int(-percent*height): , :]

    n, s, w, e = 0, image.shape[0], 0, image.shape[1]
    horizontal_angles = np.linspace(1.55, 1.59, 30)  # ~pi/2 so ~horizontal.
    vertical_angles = np.linspace(-0.02, 0.02, 30)  # ~0 so ~vertical.

    if 'N' in sides:
        data = skimage.transform.hough_line(t, horizontal_angles)
        _, _, dists = skimage.transform.hough_line_peaks(*data, num_peaks=2)
        n = int(min(dists))
    if 'S' in sides:
        data = skimage.transform.hough_line(b, horizontal_angles)
        _, _, dists = skimage.transform.hough_line_peaks(*data, num_peaks=2)
        s = image.shape[0] + int(max(dists)) - b.shape[0]
    if 'W' in sides:
        data = skimage.transform.hough_line(l, vertical_angles)
        _, _, dists = skimage.transform.hough_line_peaks(*data, num_peaks=2)
        w = int(min(dists))
    if 'E' in sides:
        data = skimage.transform.hough_line(r, vertical_angles)
        _, _, dists = skimage.transform.hough_line_peaks(*data, num_peaks=2)
        e = image.shape[1] + int(max(dists)) - r.shape[1]

    #from PIL import Image, ImageDraw
    #im = Image.fromarray(np.uint8(image * 255))
    #draw = ImageDraw.Draw(im)
    #draw.line((0, n, im.size[0], n), width=10, fill='Red')
    #draw.line((0, s, im.size[0], s), width=10, fill='Red')
    #draw.line((w, 0, w, im.size[1]), width=10, fill='Red')
    #draw.line((e, 0, e, im.size[1]), width=10, fill='Red')
    #im.save('x.png')
    #Image.fromarray(np.uint8(t * 255)).save('t.png')

    return image[n:s, w:e]


def save_image(image, filename):
    from PIL import Image
    im = Image.fromarray(image)
    im.save(filename)
