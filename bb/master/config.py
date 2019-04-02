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

import sys
from enum import Enum

import factories
from bb.utils import Mode

from common import msdk_secrets
from common.helper import Product_type, Build_type
from common.mediasdk_directories import MediaSdkDirectories


CURRENT_MODE = Mode.PRODUCTION_MODE
# CURRENT_MODE = Mode.TEST_MODE

if CURRENT_MODE == Mode.PRODUCTION_MODE:
    MEDIASDK_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/buildbot/"

elif CURRENT_MODE == Mode.TEST_MODE:
    MEDIASDK_REPO = "flow_test"
    BUILDBOT_URL = "http://mediasdk.intel.com/auxbb/"
else:
    sys.exit(f"Mode {CURRENT_MODE} is not defined")

PRODUCT_CONFIGS_REPO = "product-configs"
PRODUCTION_REPOS = [PRODUCT_CONFIGS_REPO, MEDIASDK_REPO]

RUN_COMMAND = "python3"
TRIGGER = 'trigger'

# Give possibility to enable/disable auto deploying infrastructure on workers
DEPLOYING_INFRASTRUCTURE = True

FACTORIES = factories.Factories(CURRENT_MODE, DEPLOYING_INFRASTRUCTURE, RUN_COMMAND)

"""
Specification of BUILDERS:
"name"              - name of build in Buildbot UI
"product_conf_file" - product_config which should be used
"product_type"      - Product type (all available types can be found in `common/helper.py`)
"build_type"        - type of build (for example: "release")
"api_latest"        - if `True` it will enable product`s `api_latest` feature
"compiler"          - compiler which should be used (env and product_config should support this key)
"compiler_version"  - version of compiler
"worker"            - worker(s) which should be used from `WORKERS`
"triggers"          - list of dicts with following keys:
    "branches"      - function takes one argument (branch)
                      function must return True if builder should be activated, otherwise False
    "repositories"  - list of repositories (str)
    "builders"      - list of builder names (str)
                      builder will be run only if all builds of specified "builders" passed  
"""

# All builders will use Triggerable scheduler by default
# To disable default scheduler add "add_triggerable_sheduler": False in builder dict
BUILDERS = {

    TRIGGER: {"factory": FACTORIES.init_trigger_factory,
              # SingleBranchScheduler will be used for this builder (see master.py), so default
              # Triggerable is not needed
              "add_triggerable_sheduler": False},

# TODO: Set correct values for dependencies
# TODO: Change triggers for mediasdk builders
#     "build-gmmlib": {
#         "factory": FACTORIES.init_build_factory,
#         "product_conf_file": "conf_linux_public.py",
#         "product_type": Product_type.PUBLIC_LINUX.value,
#         "build_type": Build_type.RELEASE.value,
#         "api_latest": False,
#         "fastboot": False,
#         "compiler": "gcc",
#         "compiler_version": "6.3.1",
#         "worker": "centos",
#         # Builder is enabled for all branches
#         'triggers': [{'repositories': PRODUCTION_REPOS,
#                       'branches': lambda branch: True}]
#     },
#
#     "build-igc": {
#         "factory": FACTORIES.init_build_factory,
#         "product_conf_file": "conf_linux_public.py",
#         "product_type": Product_type.PUBLIC_LINUX.value,
#         "build_type": Build_type.RELEASE.value,
#         "api_latest": False,
#         "fastboot": False,
#         "compiler": "gcc",
#         "compiler_version": "6.3.1",
#         "worker": "centos",
#         # Builder is enabled for all branches
#         'triggers': [{'repositories': PRODUCTION_REPOS,
#                       'branches': lambda branch: True}]
#     },
#
#     "build-LibVa": {
#         "factory": FACTORIES.init_build_factory,
#         "product_conf_file": "conf_linux_public.py",
#         "product_type": Product_type.PUBLIC_LINUX.value,
#         "build_type": Build_type.RELEASE.value,
#         "api_latest": False,
#         "fastboot": False,
#         "compiler": "gcc",
#         "compiler_version": "6.3.1",
#         "worker": "centos",
#         # Builder is enabled for all branches
#         'triggers': [{'repositories': PRODUCTION_REPOS,
#                       'branches': lambda branch: True}]
#     },
#
#     "build-driver": {
#         "factory": FACTORIES.init_build_factory,
#         "product_conf_file": "conf_linux_public.py",
#         "product_type": Product_type.PUBLIC_LINUX.value,
#         "build_type": Build_type.RELEASE.value,
#         "api_latest": False,
#         "fastboot": False,
#         "compiler": "gcc",
#         "compiler_version": "6.3.1",
#         "worker": "centos",
#         # Builder is enabled for all branches
#         'triggers': [{'repositories': PRODUCTION_REPOS,
#                       'branches': lambda branch: True,
#                       'builders': ['build-LibVa', 'build-gmmlib']}]
#     },
#
#     "build-OpenCL": {
#         "factory": FACTORIES.init_build_factory,
#         "product_conf_file": "conf_linux_public.py",
#         "product_type": Product_type.PUBLIC_LINUX.value,
#         "build_type": Build_type.RELEASE.value,
#         "api_latest": False,
#         "fastboot": False,
#         "compiler": "gcc",
#         "compiler_version": "6.3.1",
#         "worker": "centos",
#         # Builder is enabled for all branches
#         'triggers': [{'repositories': PRODUCTION_REPOS,
#                       'branches': lambda branch: True,
#                       'builders': ['build-igc']}]
#     },

    "build": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # Builder is enabled for all branches
        # TODO: create class for triggers
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: True}]
    },

    "build-api-next": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": True,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # Builder is enabled for not release branches
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: not MediaSdkDirectories.is_release_branch(branch)}]
    },

    "build-gcc-8.2.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "8.2.0",
        "worker": "ubuntu",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: not MediaSdkDirectories.is_release_branch(branch)}]
    },

    "build-clang-6.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_CLANG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "clang",
        "compiler_version": "6.0",
        "worker": "ubuntu",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: not MediaSdkDirectories.is_release_branch(branch)}]
    },

    # Fastboot is a special configuration of MediaSDK, when we 
    # build MediaSDK in small scope but it can load very fast
    # (needed by embedded systems)
    # see method of building it in product-config

    "build-fastboot": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_FASTBOOT.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": True,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # mss2018_r2 branch not supported building fastboot configuration
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: branch != 'mss2018_r2'}]
    },

    "build-fastboot-gcc-8.2.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_FASTBOOT_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": True,
        "compiler": "gcc",
        "compiler_version": "8.2.0",
        "worker": "ubuntu",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: not MediaSdkDirectories.is_release_branch(branch)}]
    },

    "build-api-next-defconfig": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT_DEFCONFIG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": True,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos_defconfig",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda branch: not MediaSdkDirectories.is_release_branch(branch)}]
    },

    "test": {
        "factory": FACTORIES.init_test_factory,
        "product_type": Product_type.PUBLIC_LINUX.value,
        "build_type": Build_type.RELEASE.value,
        "worker": "centos_test",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda x: True,
                      'builders': ['build']}]
    },

    "test-api-next": {
        "factory": FACTORIES.init_test_factory,
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT.value,
        "build_type": Build_type.RELEASE.value,
        "worker": "centos_test",
        'triggers': [{'repositories': PRODUCTION_REPOS,
                      'branches': lambda x: True,
                      'builders': ['build-api-next']}]
    }
}

FLOW = factories.Flow(BUILDERS, FACTORIES)

WORKERS = {
    "centos": {
        "b-1-10": {},
        "b-1-22": {}
    },
    "centos_defconfig": {
        # Workaroud for running 'trigger' builder in parallel with build
        "b-1-20": {'max_builds': 2},
    },
    "ubuntu": {
        "b-1-18": {},
        "b-1-18aux": {}
    },
    "centos_test": {
        "t-1-17": {},
        "t-1-16": {}
    },
}

PORT = "5000"
WORKER_PORT = "9000"
BUILDBOT_NET_USAGE_DATA = None  # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None  # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media SDK"

# Don't decrease the POLL_INTERVAL, because Github rate limit can be reached
# and new api requests will not be performed
POLL_INTERVAL = 20  # Poll Github for new changes (in seconds)

WORKER_PASS = msdk_secrets.WORKER_PASS
DATABASE_PASSWORD = msdk_secrets.DATABASE_PASSWORD
DATABASE_URL = f"postgresql://buildbot:{DATABASE_PASSWORD}@localhost/buildbot"
GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN
MEDIASDK_ORGANIZATION = "Intel-Media-SDK"

TRIGGER = 'trigger'

GITHUB_REPOSITORY = f"{MEDIASDK_ORGANIZATION}/{MEDIASDK_REPO}"
REPO_URL = f"https://github.com/{GITHUB_REPOSITORY}"
PRODUCT_CONFIGS_REPO_URL = f"https://github.com/{MEDIASDK_ORGANIZATION}/{PRODUCT_CONFIGS_REPO}.git"
