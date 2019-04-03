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

from enum import Enum

from common import msdk_secrets
from common.helper import Product_type, Build_type


class Mode(Enum):
    PRODUCTION_MODE = "production_mode"
    TEST_MODE = "test_mode"

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
"branch"            - function takes one argument (branch)
                      function must return True if builder should be activated, otherwise False
"""
BUILDERS = [
    {
        "name": "build",
        "product_conf_file": "driver/conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # Builder is enabled for all branches
        "branch": lambda branch: True
    }
]

TESTERS = [
    {
        "name": "test",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE.value,
        "worker": "centos_test"
    }
]

WORKER_PASS = msdk_secrets.WORKER_PASS
WORKERS = {
    "centos": {
        "b-1-14": {}
    },
    "centos_test": {
        "t-1-17": {}
    }
}

TRIGGER = 'trigger'
RUN_COMMAND = "python3"
PORT = "6000"
WORKER_PORT = "6100"
BUILDBOT_NET_USAGE_DATA = None # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media Driver"

# Don't decrease the POLL_INTERVAL, because Github rate limit can be reached
# and new api requests will not be performed
POLL_INTERVAL = 60 # Poll Github for new changes (in seconds)

DATABASE_PASSWORD = msdk_secrets.DATABASE_PASSWORD
DATABASE_URL = f"postgresql://buildbot:{DATABASE_PASSWORD}@localhost/driver_buildbot"

REPO_URL = 'https://github.com/intel/media-driver'

GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN

BUILDBOT_URL = "http://mediasdk.intel.com/driver/"

CURRENT_MODE = Mode.PRODUCTION_MODE

MEDIASDK_ORGANIZATION = "Intel-Media-SDK"
PRODUCT_CONFIGS_REPO = "product-configs"

DRIVER_ORGANIZATION = 'intel'
DRIVER_REPO = 'media-driver'

# Give possibility to enable/disable auto deploying infrastructure on workers
DEPLOYING_INFRASTRUCTURE = True
