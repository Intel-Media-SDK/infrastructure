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

import msdk_secrets

class Mode(Enum):
    PRODUCTION_MODE = "production_mode"
    PRODUCTION_MODE_PRIVATE = "production_mode_private"
    TEST_MODE = "test_mode"

BUILDERS = {
    "build_master": {
        "name": "build-master-branch",
        "product_conf_file": "conf_linux_public.py",
        "product_type": "linux", # Product type of master (branch) build
        "build_type": "release",
        "api_latest": False,
        "compiler": None,
        "compiler_version": None,
        "branch": "master",
        "worker": "build" #TODO: change
    },

    "build_not_master": {
        "name": "build",
        "product_conf_file": "conf_linux_public.py",
        "product_type": "linux", # Product type of master (branch) build
        "build_type": "release",
        "api_latest": False,
        "compiler": None,
        "compiler_version": None,
        "branch": "(?!master)",
        "worker": "build" #TODO: change
    },

    "build_api_latest": {
        "name": "build-api-next",
        "product_conf_file": "conf_linux_public.py",
        "product_type": "api_latest", # Product type of master (branch) build
        "build_type": "release",
        "api_latest": True,
        "compiler": None,
        "compiler_version": None,
        "branch": ".+?",
        "worker": "build" #TODO: change
    },

    "build_gcc_latest": {
        "name": "build-gcc-8.1.0",
        "product_conf_file": "conf_linux_public.py",
        "product_type": "linux_gcc_latest", # Product type of master (branch) build
        "build_type": "release",
        "api_latest": False,
        "compiler": "gcc",
        "compiler_version": "8.1.0",
        "branch": ".+?",
        "worker": "ubuntu" #TODO: change
    },

    "build_clang_latest": {
        "name": "build-clang-6.0",
        "product_conf_file": "conf_linux_public.py",
        "product_type": "linux_clang_latest", # Product type of master (branch) build
        "build_type": "release",
        "api_latest": False,
        "compiler": "clang",
        "compiler_version": "6.0",
        "branch": ".+?",
        "worker": "ubuntu" #TODO: change
    }
}

TESTERS = {
    "test": {
        "name": "test",
        "product_type": "linux", # Product type of master (branch) build
        "build_type": "release",
    },

    "test_api_latest": {
        "name": "test-api-next",
        "product_type": "api_latest", # Product type of master (branch) build
        "build_type": "release",
    }
}


WORKERS = {
    "build": {
        "b-1-10": {},
        "b-1-14": {}
    },
    "ubuntu": {
        "b-1-18": {}
    },
    "test": {
        "t-1-17": {},
        "t-1-16": {}
    }
}


RUN_COMMAND = "python3"
PORT = "5000"
WORKER_PORT = "9000"
BUILDBOT_NET_USAGE_DATA = None # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media SDK"

POLL_INTERVAL = 10 # Poll Github for new changes (in seconds)

WORKER_PASS = msdk_secrets.WORKER_PASS
DATABASE_PASSWORD = msdk_secrets.DATABASE_PASSWORD
DATABASE_URL = f"postgresql://buildbot:{DATABASE_PASSWORD}@localhost/buildbot"
GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN
GITHUB_OWNER = "Intel-Media-SDK"

CURRENT_MODE = Mode.PRODUCTION_MODE
#CURRENT_MODE = Mode.PRODUCTION_MODE_PRIVATE
#CURRENT_MODE = Mode.TEST_MODE

if CURRENT_MODE == Mode.PRODUCTION_MODE:
    GITHUB_OWNERS_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/buildbot/"

elif CURRENT_MODE == Mode.PRODUCTION_MODE_PRIVATE:
    BUILDBOT_TITLE = "MediaSDK Private"
    WORKERS = {"build": {"b-50-41": {},
                         "b-50-61": {}},
               "ubuntu": {"b-999-999": {}},
               "test": {"t-999-999": {}}}
    GITHUB_OWNERS_REPO = msdk_secrets.EMBEDDED_REPO
    BUILDBOT_URL = msdk_secrets.BUILDBOT_URL
    MASTER_PRODUCT_TYPE = "embedded_private"

elif CURRENT_MODE == Mode.TEST_MODE:
    GITHUB_OWNERS_REPO = "flow_test"
    BUILDBOT_URL = "http://mediasdk.intel.com/auxbb/"
else:
    sys.exit(f"Mode {CURRENT_MODE} is not defined")

GITHUB_REPOSITORY = f"{GITHUB_OWNER}/{GITHUB_OWNERS_REPO}"
REPO_URL = f"https://github.com/{GITHUB_REPOSITORY}"
REPO_INFO = f"{GITHUB_OWNERS_REPO}:%(prop:branch)s:%(prop:revision)s"
