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
This module checks existence of component on share
"""

import sys
import logging
import argparse
import pathlib

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common.manifest_manager import Manifest, get_build_dir, get_build_url
from common.helper import ErrorCode, Product_type
from common.logger_conf import configure_logger
from bb.utils import SKIP_BUILDING_DEPENDENCY_PHRASE


def check_component_existence(path_to_manifest, component_name, product_type):
    log = logging.getLogger('component_checker')
    log.info(f"Getting data for {component_name} from {path_to_manifest}")
    manifest = Manifest(pathlib.Path(path_to_manifest))

    if product_type:
        manifest.get_component(component_name).build_info.set_product_type(product_type)

    component_dir = get_build_dir(manifest, component_name)
    if component_dir.exists():
        log.info(f"Directory {component_dir} exists")
        link_to_artifacts = get_build_url(manifest, component_name)
        log.info(f"Artifacts are available by: {link_to_artifacts}")
        # This is stop phrase for buildbot to skip all build stages
        log.info(SKIP_BUILDING_DEPENDENCY_PHRASE)
    else:
        log.info(f"Directory {component_dir} doesn't exist")


def main():
    parser = argparse.ArgumentParser(prog="component_checker.py",
                                     description='Checks existence of component on share',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-m', '--path-to-manifest', help='Path to manifest file', required=True)
    parser.add_argument('-c', '--component-name', help='Component name to check', required=True)
    parser.add_argument('-p', '--product-type',
                        choices=[product_type.value for product_type in Product_type],
                        help='Type of product')
    args = parser.parse_args()

    configure_logger()
    log = logging.getLogger('component_checker.main')

    try:
        check_component_existence(args.path_to_manifest, args.component_name, args.product_type)
    except Exception:
        log.exception('Exception occurred')
        exit(ErrorCode.CRITICAL.value)
    exit(0)


if __name__ == '__main__':
    main()
