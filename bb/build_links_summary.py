# Copyright (c) 2019 Intel Corporation
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

"""
Links generator for build artifacts
"""

import sys
import pathlib
import argparse

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common.manifest_manager import Manifest, get_build_url
from common.helper import ErrorCode


COMPONENTS_LIST = [
    'mediasdk',
    'media-driver',
    'libva',
    'libva-utils',
    'gmmlib',
    'ffmpeg',
    'metrics_calc_lite',
    'opencl_runtime'
]


def generate_build_links(manifest):
    """
    Get and print url to artifacts for each component

    :param manifest: Path to manifest.yml
    :type manifest: String

    :return: Boolean
    """

    try:
        manifest = Manifest(manifest)

        print('*' * 50)
        for component in COMPONENTS_LIST:
            print(f'{component}: {get_build_url(manifest, component)}')
        print('*' * 50)
    except Exception:
        return False
    return True


def main():
    """
    Arguments parser and links generator runner
    """

    parser = argparse.ArgumentParser(prog="build_links_summary.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-m', "--manifest", metavar="PATH", required=True,
                        help="Path to manifest.yml file")
    args = parser.parse_args()

    if not generate_build_links(args.manifest):
        exit(ErrorCode.CRITICAL.value)


if __name__ == '__main__':
    main()
