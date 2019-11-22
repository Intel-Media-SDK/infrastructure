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

import sys

from bb import factories
from bb.utils import Mode, CIService, GithubCommitFilter

from common import msdk_secrets
from common.helper import Product_type, Build_type
from common.mediasdk_directories import MediaSdkDirectories, OsType

# TODO: use this variable in notifications and other services
CI_SERVICE = CIService.MEDIASDK
CURRENT_MODE = Mode.PRODUCTION_MODE
# CURRENT_MODE = Mode.TEST_MODE

if CURRENT_MODE == Mode.PRODUCTION_MODE:
    MEDIASDK_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/buildbot/"

elif CURRENT_MODE == Mode.TEST_MODE:
    MEDIASDK_REPO = "MediaSDK"
    BUILDBOT_URL = "http://mediasdk.intel.com/auxbb/"
else:
    sys.exit(f"Mode {CURRENT_MODE} is not defined")

MEDIASDK_ORGANIZATION = "Intel-Media-SDK"
INFRASTRUCTURE_REPO = "infrastructure"
PRODUCT_CONFIGS_REPO = "product-configs"

INTEL_ORGANIZATION = 'intel'
DRIVER_REPO = 'media-driver'
LIBVA_REPO = 'libva'
GMMLIB_REPO = 'gmmlib'

# We haven't CI for these repositories, but we update its revisions in manifest automatically.
# This feature should work for master branch only.

AUTO_UPDATED_REPOSITORIES = [LIBVA_REPO, GMMLIB_REPO]

PRODUCTION_REPOS = [PRODUCT_CONFIGS_REPO, MEDIASDK_REPO, DRIVER_REPO]

PYTHON_EXECUTABLE = {OsType.linux: r'python3',
                     OsType.windows: r'py'}
TRIGGER = 'trigger'

# Give possibility to enable/disable auto deploying infrastructure on workers
DEPLOYING_INFRASTRUCTURE = True

FACTORIES = factories.Factories(CURRENT_MODE, DEPLOYING_INFRASTRUCTURE,
                                PYTHON_EXECUTABLE, CI_SERVICE, AUTO_UPDATED_REPOSITORIES)

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

    "build-libva": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_libva.py",
        "product_type": Product_type.PUBLIC_LINUX_LIBVA.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # TODO: rename to component_name
        "dependency_name": 'libva',
        # Builder is enabled for all branches
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-libva-utils": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_libva_utils.py",
        "product_type": Product_type.PUBLIC_LINUX_LIBVA_UTILS.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        # TODO: rename to component_name
        "dependency_name": 'libva-utils',
        # Builder is enabled for all branches
        'triggers': [{'builders': ["build-libva"],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-gmmlib": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_gmmlib.py",
        "product_type": Product_type.PUBLIC_LINUX_GMMLIB.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'gmmlib',
        # Builder is enabled for all branches
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-igc": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_igc.py",
        "product_type": Product_type.PUBLIC_LINUX_IGC.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'intel-graphics-compiler',
        # Builder is enabled for master and intel-mediasdk-19.1
        'triggers': [{'filter': GithubCommitFilter(
            PRODUCTION_REPOS,
            lambda branch, target_branch: (target_branch or branch) in ['master', 'intel-mediasdk-19.1'])}]
    },

    "build-opencl": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_opencl.py",
        "product_type": Product_type.PUBLIC_LINUX_OPENCL_RUNTIME.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'opencl_runtime',
        # Builder is enabled for master and intel-mediasdk-19.1, see build-igc
        'triggers': [{'builders': ['build-igc', 'build-gmmlib'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-ffmpeg": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_ffmpeg.py",
        "product_type": Product_type.PUBLIC_LINUX_FFMPEG.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'ffmpeg',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-metrics-calc": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_metrics_calc.py",
        "product_type": Product_type.PUBLIC_LINUX_METRICS_CALC.value,
        "build_type": Build_type.RELEASE.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'metrics_calc_lite',
        # Builder is enabled for all branches
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-driver": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['build-libva', 'build-gmmlib'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-driver-gcc-9.2.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "9.2.0",
        "worker": "ubuntu",
        "dependency_name": 'media-driver',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['build-libva', 'build-gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "build-driver-clang-9.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER_CLANG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "clang",
        "compiler_version": "9",
        "worker": "ubuntu",
        "dependency_name": 'media-driver',
        # Builder is enabled for all branches
        'triggers': [{'builders': ['build-libva', 'build-gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "build-driver-debug": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.DEBUG.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        # TODO: create class for triggers
        'triggers': [{'builders': ['build-libva', 'build-gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "build-driver-release-internal": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_media_driver.py",
        "product_type": Product_type.PUBLIC_LINUX_DRIVER.value,
        "build_type": Build_type.RELEASE_INTERNAL.value,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'media-driver',
        # TODO: create class for triggers
        'triggers': [{'builders': ['build-libva', 'build-gmmlib'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "build-mediasdk": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'mediasdk',
        # Builder is enabled for all branches
        # TODO: create class for triggers
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: True)}]
    },

    "build-mediasdk-api-next": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": True,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos",
        "dependency_name": 'mediasdk',
        # Builder is enabled for not release branches
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "build-gcc-9.2.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "9.2.0",
        "worker": "ubuntu",
        "dependency_name": 'mediasdk',
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "build-clang-9.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_CLANG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": False,
        "compiler": "clang",
        "compiler_version": "9",
        "worker": "ubuntu",
        "dependency_name": 'mediasdk',
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
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
        "dependency_name": 'mediasdk',
        # mss2018_r2 branch not supported building fastboot configuration
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) != 'mss2018_r2')}]
    },

    "build-fastboot-gcc-9.2.0": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_FASTBOOT_GCC_LATEST.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": False,
        "fastboot": True,
        "compiler": "gcc",
        "compiler_version": "9.2.0",
        "worker": "ubuntu",
        "dependency_name": 'mediasdk',
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "build-mediasdk-api-next-defconfig": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_linux_public.py",
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT_DEFCONFIG.value,
        "build_type": Build_type.RELEASE.value,
        "api_latest": True,
        "fastboot": False,
        "compiler": "gcc",
        "compiler_version": "6.3.1",
        "worker": "centos_defconfig",
        "dependency_name": 'mediasdk',
        'triggers': [{'builders': ['build-libva'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: not MediaSdkDirectories.is_release_branch(
                              target_branch or branch))}]
    },

    "build-windows": {
        "factory": FACTORIES.init_build_factory,
        "product_conf_file": "conf_windows_public.py",
        "product_type": Product_type.PUBLIC_WINDOWS.value,
        "build_type": Build_type.RELEASE.value,
        "worker": "windows",
        "dependency_name": 'mediasdk',
        # Builder is enabled for all branches
        'triggers': [{'filter': GithubCommitFilter(PRODUCTION_REPOS,
                                                   lambda branch, target_branch: (target_branch or branch) == 'master')}]
    },

    "test": {
        "factory": FACTORIES.init_test_factory,
        "product_type": Product_type.PUBLIC_LINUX.value,
        "build_type": Build_type.RELEASE.value,
        "product_conf_file": "conf_media_test.py",
        "custom_types": f"mediasdk:{Product_type.PUBLIC_LINUX.value}",
        "worker": "centos_test",
        # build-opencl is dependecy only for master and intel-mediasdk-19.1 branches,
        # because for other branches that build doesn't run
        'triggers': [{'builders': ['build-mediasdk', 'build-driver'],
                      'filter': GithubCommitFilter(
            PRODUCTION_REPOS,
            lambda branch, target_branch: (target_branch or branch) not in ['master', 'intel-mediasdk-19.1'])},
                     
                     {'builders': ['build-mediasdk', 'build-driver', 'build-opencl',
                                   'build-libva-utils'],
                      'filter': GithubCommitFilter(
            PRODUCTION_REPOS,
            lambda branch, target_branch: (target_branch or branch) in ['master', 'intel-mediasdk-19.1'])}]
    },

    "test-api-next": {
        "factory": FACTORIES.init_test_factory,
        "product_type": Product_type.PUBLIC_LINUX_API_NEXT.value,
        "build_type": Build_type.RELEASE.value,
        "product_conf_file": "conf_media_test.py",
        "custom_types": f"mediasdk:{Product_type.PUBLIC_LINUX_API_NEXT.value}",
        "worker": "centos_test",
        'triggers': [{'builders': ['build-mediasdk', 'build-driver', 'build-opencl',
                                   'build-libva-utils'],
                      'filter': GithubCommitFilter(PRODUCTION_REPOS, 
                                                   lambda branch, target_branch: True)}]},

    "packages": {
        "factory": FACTORIES.init_package_factory,
        "worker": "ubuntu",
        'triggers': [{'builders': ['test-api-next', 'test'],
                      'filter': GithubCommitFilter(
                          PRODUCTION_REPOS,
                          lambda branch, target_branch: (target_branch or branch) == 'master')}]},
}

FLOW = factories.Flow(BUILDERS, FACTORIES)

WORKERS = {
    "windows": {
        'b-1-26': {"os": OsType.windows},
        'b-1-27': {"os": OsType.windows},
    },

    "centos": {
        "b-1-10": {"os": OsType.linux},
        "b-1-14": {"os": OsType.linux},
        "b-1-22": {"os": OsType.linux}
    },
    "centos_defconfig": {
        # Workaroud for running 'trigger' builder in parallel with build
        "b-1-23": {"os": OsType.linux, 'max_builds': 2},
    },
    "ubuntu": {
        "b-1-18": {"os": OsType.linux},
        "b-1-18aux": {"os": OsType.linux},
        "b-1-24": {"os": OsType.linux}
    },
    "centos_test": {
        "t-1-17": {"os": OsType.linux},
        "t-1-16": {"os": OsType.linux}
    },
}

PORT = "5000"
WORKER_PORT = "9000"
BUILDBOT_NET_USAGE_DATA = None  # "None" disables the sending of usage analysis info to buildbot.net
BUILDBOT_TREE_STABLE_TIMER = None  # Value "None" means that a separate build will be started immediately for each Change.
BUILDBOT_TITLE = "Intel® Media CI"

# Don't decrease the POLL_INTERVAL, because Github rate limit can be reached
# and new api requests will not be performed
POLL_INTERVAL = 60  # Poll Github for new changes (in seconds)

WORKER_PASS = msdk_secrets.WORKER_PASS
DATABASE_URL = f"postgresql://buildbot:{msdk_secrets.DATABASE_PASSWORD}@localhost/buildbot"
GITHUB_TOKEN = msdk_secrets.GITHUB_TOKEN

TRIGGER = 'trigger'

REPO_URL = f"https://github.com/{MEDIASDK_ORGANIZATION}/{MEDIASDK_REPO}"
