# -*- coding: utf-8 -*-

import sys
import os
import struct
import io
import subprocess
import contextlib
from urllib.request import urlopen
from term_plot import iterm2


def get_image_shape(buf):
    """
    Extracts image shape as 2-tuple (width, height) from the content buffer.

    Supports GIF, PNG and other image types (e.g. JPEG) if PIL/Pillow is installed.
    Returns (None, None) if it can't be identified.
    """
    def _unpack(fmt, buffer, mode='Image'):
        try:
            return struct.unpack(fmt, buffer)
        except struct.error:
            raise ValueError("Invalid {} file".format(mode))

    # TODO: handle 'stream-like' data efficiently, not storing all the content into memory
    buf_len = len(buf)

    if buf_len >= 10 and buf[:6] in (b'GIF87a', b'GIF89a'):
        return _unpack("<hh", buf[6:10], mode='GIF')
    elif buf_len >= 24 and buf.startswith(b'\211PNG\r\n\032\n') and buf[12:16] == b'IHDR':
        return _unpack(">LL", buf[16:24], mode='PNG')
    elif buf_len >= 16 and buf.startswith(b'\211PNG\r\n\032\n'):
        return _unpack(">LL", buf[8:16], mode='PNG')
    else:
        # everything else: get width/height from PIL
        # TODO: it might be inefficient to write again the memory-loaded content to buffer...
        b = io.BytesIO()
        b.write(buf)

        try:
            from PIL import Image
        except ImportError:
            # PIL not available
            sys.stderr.write("Warning: cannot determine the image size; please install Pillow\n")
            sys.stderr.flush()
            b.close()
            return None, None

        try:
            im = Image.open(b)
            return im.width, im.height
        except (IOError, OSError) as ex:
            # PIL.Image.open throws an error -- probably invalid byte input are given
            sys.stderr.write(f"Warning: PIL cannot identify image; this may not be an image file. Message: {ex}\n")
        finally:
            b.close()

        return None, None


def _isinstance(obj, module, clsname):
    """A helper that works like isinstance(obj, module:clsname), but even when
    the module hasn't been imported or the type is not importable."""

    if module not in sys.modules:
        return False

    try:
        clstype = getattr(sys.modules[module], clsname)
        return isinstance(obj, clstype)
    except AttributeError:
        return False


def to_content_buf(data):
    # TODO: handle 'stream-like' data efficiently, rather than storing into RAM

    if isinstance(data, bytes):
        return data
    elif isinstance(data, io.BufferedReader):
        buf = data
        return buf.read()
    elif isinstance(data, io.TextIOWrapper):
        return data.buffer.read()

    elif _isinstance(data, 'numpy', 'ndarray'):
        # numpy ndarray: convert to png
        im = data
        if len(im.shape) == 2:
            mode = 'L'     # 8-bit pixels, grayscale
            im = im.astype(sys.modules['numpy'].uint8)
        elif len(im.shape) == 3 and im.shape[2] in (3, 4):
            mode = None    # RGB/RGBA
            if im.dtype.kind == 'f':
                im = (im * 255).astype('uint8')
        else:
            raise ValueError("Expected a 3D ndarray (RGB/RGBA image) or 2D (grayscale image), "
                             "but given shape: {}".format(im.shape))

        try:
            from PIL import Image
        except ImportError as e:
            # TODO; reraise
            raise ImportError(f"\n{e.msg}To draw numpy arrays, we require Pillow. (pip install Pillow)")

        with io.BytesIO() as buf:
            # mode: https://pillow.readthedocs.io/en/4.2.x/handbook/concepts.html#concept-modes
            Image.fromarray(im, mode=mode).save(buf, format='png')
            return buf.getvalue()

    elif _isinstance(data, 'torch', 'Tensor'):
        im = data
        return to_content_buf(im.numpy())

    elif _isinstance(data, 'tensorflow.python.framework.ops', 'EagerTensor'):
        im = data
        return to_content_buf(im.numpy())

    elif _isinstance(data, 'PIL.Image', 'Image'):
        # PIL/Pillow images
        img = data

        with io.BytesIO() as buf:
            img.save(buf, format='png')
            return buf.getvalue()

    elif _isinstance(data, 'matplotlib.figure', 'Figure'):
        # matplotlib figures
        fig = data
        if fig.canvas is None:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            FigureCanvasAgg(fig)

        with io.BytesIO() as buf:
            fig.savefig(buf)
            return buf.getvalue()

    else:
        raise TypeError("Unsupported type : {}".format(type(data)))


def get_tty_size():
    rows, columns = subprocess.check_output(['stty', 'size']).split()
    return int(rows), int(columns)


def imgcat(data, filename=None, width=None, height=None, preserve_aspect_ratio=True, pixels_per_line=24, fp=None):
    """
    Print image on terminal (iTerm2).

    Follows the file-transfer protocol of iTerm2 described at
    https://www.iterm2.com/documentation-images.html.

    Args:
        data: the content of image in buffer interface, numpy array, etc.
        filename: the image file name.
        width: the width for displaying image, in number of characters (columns)
        height: the height for displaying image, in number of lines (rows)
        preserve_aspect_ratio: whether to preserve aspect ratio.
        pixels_per_line: the number of pixels per line.
        fp: The buffer to write to, defaults `sys.stdout`
    """
    if fp is None:
        fp = sys.stdout.buffer  # for stdout, use buffer interface (py3)

    buf = to_content_buf(data)
    if len(buf) == 0:
        raise ValueError("Empty buffer")

    if height is None:
        im_width, im_height = get_image_shape(buf)
        if im_height:
            assert pixels_per_line > 0
            height = (im_height + (pixels_per_line - 1)) // pixels_per_line

            # automatically limit height to the current tty,
            # otherwise the image will be just erased
            try:
                tty_height, _ = get_tty_size()
                height = max(1, min(height, tty_height - 9))
            except OSError as e:
                print(e)
                # may not be a terminal
                pass
        else:
            # image height unavailable, fallback?
            height = 10

    iterm2.write_image(buf, fp,
                       filename=filename, width=width, height=height,
                       preserve_aspect_ratio=preserve_aspect_ratio)


def main():
    import argparse
    try:
        from imgcat import __version__
    except ImportError:
        __version__ = 'N/A'

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='*', type=str,
                        help='Path to the images.')
    parser.add_argument('--height', default=None, type=int,
                        help='The number of rows (in terminal) for displaying images.')
    parser.add_argument('--width', default=None, type=int,
                        help='The number of columns (in terminal) for displaying images.')
    parser.add_argument('-v', '--version', action='version',
                        version='term-plot %s' % __version__)
    args = parser.parse_args()

    kwargs = dict()
    if args.height:
        kwargs['height'] = args.height
    if args.width:
        kwargs['width'] = args.width

    # read from stdin?
    if not sys.stdin.isatty():
        if not args.input or list(args.input) == ['-']:
            stdin = sys.stdin.buffer
            imgcat(to_content_buf(stdin), **kwargs)
            return 0

    # imgcat from arguments
    for fname in args.input:
        # filename: open local file or download from web
        try:
            # noinspection HttpUrlsUsage
            if fname.startswith('http://') or fname.startswith('https://'):
                with contextlib.closing(urlopen(fname)) as fp:
                    buf = fp.read()  # pylint: disable=no-member
            else:
                with io.open(fname, 'rb') as fp:
                    buf = fp.read()
        except IOError as e:
            sys.stderr.write(str(e))
            sys.stderr.write('\n')
            return e.errno or 1

        imgcat(buf, filename=os.path.basename(fname), **kwargs)

    if not args.input:
        parser.print_help()

    return 0


if __name__ == '__main__':
    sys.exit(main())
