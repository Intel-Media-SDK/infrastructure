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
from common.mediasdk_directories import MediaSdkDirectories
from common.manifest_manager import Manifest
from common.helper import Build_type, Build_event, ErrorCode
from common.logger_conf import configure_logger
from bb.utils import SKIP_BUILDING_DEPENDENCY_PHRASE


def check_component_existence(path_to_manifest, component_name):
    log = logging.getLogger('component_checker')
    log.info(f"Getting data for {component_name} from {path_to_manifest}")
    manifest = Manifest(pathlib.Path(path_to_manifest))
    component = manifest.get_component(component_name)
    repository = component.get_repository(component_name)
    component_dir = MediaSdkDirectories.get_build_dir(
        repository.branch,
        Build_event.COMMIT.value,
        repository.revision,
        component.product_type,
        Build_type.RELEASE.value,
        product=component_name)
    if component_dir.exists():
        log.info(f"Directory {component_dir} exists")
        # This is stop phrase for buildbot to skip all build stages
        log.info(SKIP_BUILDING_DEPENDENCY_PHRASE)
    else:
        log.info(f"Directory {component_dir} doesn't exist")


def main():
    parser = argparse.ArgumentParser(prog="component_checker.py",
                                     description='Checks existence of component on share',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-p', '--path-to-manifest', help='Path to manifest file', required=True)
    parser.add_argument('-c', '--component-name', help='Component name to check', required=True)
    args = parser.parse_args()

    configure_logger()
    log = logging.getLogger('component_checker.main')

    try:
        check_component_existence(args.path_to_manifest, args.component_name)
    except Exception:
        log.exception('Exception occurred')
        exit(ErrorCode.CRITICAL.value)
    exit(0)


if __name__ == '__main__':
    main()
