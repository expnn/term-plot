"""
iTerm2 backend for imgcat.
"""

import os
import io
import sys
import base64
from matplotlib.figure import Figure
from base64 import standard_b64encode

TMUX_WRAP_ST = b'\033Ptmux;'
TMUX_WRAP_ED = b'\033\\'

OSC = b'\033]'
CSI = b'\033['
ST = b'\a'      # \a = ^G (bell)


def write_image(buf, fp, filename, width, height, preserve_aspect_ratio):
    # need to detect tmux
    is_tmux = 'TMUX' in os.environ and 'tmux' in os.environ['TMUX']

    # tmux: print some margin and the DCS escape sequence for passthrough
    # In tmux mode, we need to first determine the number of actual lines
    if is_tmux:
        fp.write(b'\n' * height)
        # move the cursers back
        fp.write(CSI + b'?25l')
        fp.write(CSI + str(height).encode() + b"F")     # PEP-461
        fp.write(TMUX_WRAP_ST + b'\033')

    # now starts the iTerm2 file transfer protocol.
    fp.write(OSC)
    fp.write(b'1337;File=inline=1')
    fp.write(b';size=' + str(len(buf)).encode())
    if filename:
        if isinstance(filename, bytes):
            filename_bytes = filename
        else:
            filename_bytes = filename.encode()
        fp.write(b';name=' + base64.b64encode(filename_bytes))
    fp.write(b';height=' + str(height).encode())
    if width:
        fp.write(b';width=' + str(width).encode())
    if not preserve_aspect_ratio:
        fp.write(b';preserveAspectRatio=0')
    fp.write(b':')
    fp.flush()

    buf_base64 = base64.b64encode(buf)
    fp.write(buf_base64)

    fp.write(ST)

    if is_tmux:
        # terminate DCS passthrough mode
        fp.write(TMUX_WRAP_ED)
        # move back the cursor lines down
        fp.write(CSI + str(height).encode() + b"E")
        fp.write(CSI + b'?25h')
    else:
        fp.write(b'\n')

    # flush is needed so that the cursor control sequence can take effect
    fp.flush()


def imshow(img, filename=None, width=None, height=None, preserve_aspect_ratio=True):
    def get_osc_st():
        if os.environ.get('TERM', '').startswith('screen'):
            return b'\033Ptmux;\033\033]', b"\a\033\\"
        else:
            return b"\033]", b"\a"

    # noinspection PyShadowingNames
    def serialize_image(img, filename=None, inline=1, print_filename=None,
                        width=None, height=None, preserve_aspect_ratio=True):
        osc, st = get_osc_st()
        out = [osc, f'1337;File=inline={inline}'.encode('ascii')]
        if filename is not None:
            out.append(f";name={standard_b64encode(filename.encode('utf8'))}".encode('ascii'))

        if width is not None:
            out.append(f";width={width}".encode('ascii'))

        if height is not None:
            out.append(f";height={height}".encode('ascii'))

        if preserve_aspect_ratio is None or preserve_aspect_ratio is True:
            preserve_aspect_ratio = 1
        else:
            preserve_aspect_ratio = int(preserve_aspect_ratio)

        out.append(f";preserveAspectRatio={preserve_aspect_ratio}".encode('ascii'))
        out.append(b':')
        base64contents = standard_b64encode(img)
        out.append(base64contents)
        out.append(st)
        out.append(b'\n')
        print_filename = print_filename and filename is not None
        if print_filename:
            out.append(filename.encode('ascii'))
        return b''.join(out)

    if isinstance(img, Figure):
        buf = io.BytesIO()
        img.savefig(buf, format='png')
        buf.seek(0)
        img = buf.read()
    elif hasattr(img, 'read'):
        img = img.read()

    assert isinstance(img, bytes), "img should be bytes, matplotlib.figure.Figure, or a readable object."
    data = serialize_image(img, filename, print_filename=(filename is not None), width=width, height=height,
                           preserve_aspect_ratio=preserve_aspect_ratio)
    sys.stdout.buffer.write(data)
    sys.stdout.flush()
