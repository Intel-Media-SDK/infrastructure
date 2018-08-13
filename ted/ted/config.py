# -*- coding: utf-8 -*-

# Copyright (c) 2018 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import pathlib

MEDIASDK_FOLDER = pathlib.Path('/opt/intel/mediasdk')
POSSIBLE_SAMPLES_FOLDER = [
    MEDIASDK_FOLDER / 'share' / 'mfx' / 'samples',
    MEDIASDK_FOLDER / 'samples',
]

def get_samples_folder():
    for samples_folder in POSSIBLE_SAMPLES_FOLDER:
        if samples_folder.exists():
            print(f"Samples found in: {samples_folder}")
            return samples_folder #success

    print(f"Samples were not found.")
    print(f"Put samples to the one of the following locations and restart ted:")
    print(config.POSSIBLE_SAMPLES_FOLDER)
    exit(1)
