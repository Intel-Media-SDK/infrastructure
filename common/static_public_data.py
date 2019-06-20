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

# TODO: remove one_ci dir before releasing new infrastructure
SHARE_PATHS = {'build_linux': r'/media/builds/one_ci',
               'test_linux': r'/media/tests/one_ci', }

REPOSITORIES = {
    # linux_open_source
    'MediaSDK': 'https://github.com/Intel-Media-SDK/MediaSDK',
    # Media SDK tools
    'tools': 'https://github.com/Intel-Media-SDK/tools.git',
    # open source libva
    'libva': 'https://github.com/intel/libva',
    # open source libva-utils
    'libva-utils': 'https://github.com/intel/libva-utils.git',
    # test_repositories
    'flow_test': 'https://github.com/Intel-Media-SDK/flow_test.git',
    # open source infrastructure repository
    'infrastructure': 'https://github.com/Intel-Media-SDK/infrastructure.git',
    # open source product configs
    'product-configs': 'https://github.com/Intel-Media-SDK/product-configs.git',
    # open source media-driver
    'media-driver': 'https://github.com/intel/media-driver.git',
    # open source gmmlib
    'gmmlib': 'https://github.com/intel/gmmlib.git',
    # open source opencl_runtime
    # Note: the codename is neo
    'opencl_runtime': 'https://github.com/intel/compute-runtime',
    
    # Dependency repos for intel-graphics-compiler
    'llvm': 'https://github.com/llvm-mirror/llvm',
    'clang': 'https://github.com/llvm-mirror/clang',
    'opencl-clang': 'https://github.com/intel/opencl-clang',
    'spirv-llvm-translator': 'https://github.com/KhronosGroup/SPIRV-LLVM-Translator',
    'llvm-patches': 'https://github.com/intel/llvm-patches',
    # open source intel-graphics-compiler
    'intel-graphics-compiler': 'https://github.com/intel/intel-graphics-compiler',
    # ffmpeg for media-driver testing
    'ffmpeg': 'https://github.com/FFmpeg/FFmpeg'
}

PROXIES = {}
OPEN_SOURCE_PRODUCT_CONFIGS_REPO = 'product-configs'
OPEN_SOURCE_INFRASTRUCTURE_REPO = 'infrastructure'
CLOSED_SOURCE_PRODUCT_CONFIGS_REPO = ''
CLOSED_SOURCE_INFRASTRUCTURE_REPO = ''
