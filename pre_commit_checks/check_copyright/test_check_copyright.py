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

""" Unit tests scope for precommit copyright check

    Usage:
    python3 -m pytest -s -v test_check_copyright.py

    See also, the copyright check test run:
    python3 check_copyright.py --repo_path ./mdp_msdk-c2-plugins --commit_id \
        6871f3feae83c1c99e03371544b2ba7bf0436aaf --report_path pre_commit_checks.jso

"""

import pathlib

from check_copyright import CopyrightChecker
from check_copyright import YEAR

from check_copyright import get_leading_comments
from check_copyright import get_copyright_strings
from check_copyright import is_intel_copyright
from check_copyright import get_copyright_year_or_range

class TestCopyrightChecker:
    """ Test class
    """
    def setup(self):
        """ Runs before any test
        """
        self.copyright_checker = CopyrightChecker("", "", "")
        self.details = []
        self.src_file = "some_file_name"
        self.copyright_checker.repo_path = pathlib.Path("/opt/test/mdp_msdk-c2-plugins")

        self.test_copyright_sampl = {

            "android_copyright_v1" : """/*
* Copyright (C) {year} The Android Open Source Project
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*      http://www.apache.org/copyrights/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/
#defile <conio.h>
""",
            "android_copyright_v2" : """/*
* copyright {year}, The Android Open Source Project
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*      http://www.apache.org/copyrights/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

#defile <iostreams>
""",
            "android_copyright_v3" : """/*
* Copyright {year} The Android Open Source Project
*
* Licensed under the Apache License, Version 2.0 (the "License");
* you may not use this file except in compliance with the License.
* You may obtain a copy of the License at
*
*      http://www.apache.org/copyrights/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS,
* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
* See the License for the specific language governing permissions and
* limitations under the License.
*/

#define ERROR 0
""",
            "android_bad_copyright" : """/*
* Copyright (C) The Android Open Source Project
*
*/
""",
            "intel_bad_copyright_v1" : """/*
//
// INTEL CORPORATION PROPRIETARY INFORMATION
//
// This software is supplied under the terms of a copyright agreement or
// nondisclosure agreement with Intel Corporation and may not be copied
// or disclosed except in accordance with the terms of that agreement.
//
// Copyright(C) 2010-2014 Intel Corporation. All Rights Reserved.
//

/* DEFAULTS */
""",
            "intel_bad_copyright_v2" : """
_ /*   */
INTEL CORPORATION PROPRIETARY INFORMATION

This software is supplied under the terms of a copyright agreement or
nondisclosure agreement with Intel Corporation and may not be copied
or disclosed except in accordance with the terms of that agreement.

Copyright(C) 2015-{year} Intel Corporation. All Rights Reserved.
*/

/* DEFAULTS */
""",
            "intel_actual_copyright_v1" : """/*
//
// INTEL CORPORATION PROPRIETARY INFORMATION
//
// This software is supplied under the terms of a copyright agreement or
// nondisclosure agreement with Intel Corporation and may not be copied
// or disclosed except in accordance with the terms of that agreement.
//
// Copyright(C) 2015-{year} Intel Corporation. All Rights Reserved.
//

class MfxValidator
""",
            "intel_actual_copyright_v2" : """
// Copyright (c) 2011-{year} Intel Corporation
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, subcopyright, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#include "mfx_omx_utils.h"
#include "mfx_omx_defaults.h"
#include "mfx_omx_venc_component.h"
#include "mfx_omx_vaapi_allocator.h"

""",
            "intel_actual_copyright_v3" : """
_/* ****************************************************************************** *\

INTEL CORPORATION PROPRIETARY INFORMATION
This software is supplied under the terms of a license agreement or nondisclosure
agreement with Intel Corporation and may not be copied or disclosed except in
accordance with the terms of that agreement
Copyright (c) 2017-2019 Intel Corporation. All Rights Reserved.
\* ****************************************************************************** */

#include "ts_encoder.h"
#include "ts_decoder.h"
#include "ts_parser.h"
#include "ts_struct.h"
#include "mfx_ext_buffers.h"
#include "gmock/test_suites/vp9e_utils.h"

namespace vp9e_temporal_scalability
"""}

        for key, val in self.test_copyright_sampl.items():
            self.test_copyright_sampl[key] = val.format(year=f"{YEAR}").splitlines()

    def test_get_copyright_strings__correct(self):
        ret = get_copyright_strings(self.test_copyright_sampl['android_copyright_v1'])
        assert ret == [f'* Copyright (C) {YEAR} The Android Open Source Project']

    def test_get_copyright_strings__correct(self):
        ret = get_copyright_strings(self.test_copyright_sampl['intel_bad_copyright_v1'])
        assert ret == [f'// Copyright(C) 2010-2014 Intel Corporation. All Rights Reserved.']

    def test_is_intel_copyright__correct(self):
        ret = is_intel_copyright(f'/* Copyright(C) 2010-{YEAR} Intel Corporation. '
                                 f'All Rights Reserved. */')
        assert ret is not None

    def test_is_intel_copyright__incorrect(self):
        ret = is_intel_copyright(f'Copyright (C) {YEAR} The Android Open Source Project')
        assert ret is None

    def test_get_copyright_year_or_range__incorrect(self):
        ret = get_copyright_year_or_range(f'Copyright (C) The Android Open Source Project')
        assert ret is None

    def test_get_copyright_year_or_range__test_year(self):
        ret = get_copyright_year_or_range(f'Copyright (C) 2015 The Android Open Source Project')
        assert ret == {'year': 2015}

    def test_get_copyright_year_or_range__test_range(self):
        ret = get_copyright_year_or_range(f'// Copyright(C) 2010-2014 Intel Corporation. '
                                          f'All Rights Reserved.')
        assert ret == {'range': [2010, 2014]}

    def test_is_copyright_correct__third_party_copyright__correct(self):
        comments = get_leading_comments(self.test_copyright_sampl['android_copyright_v1'])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is True

    def test_is_copyright_correct__third_party_copyright__correct_2(self):
        comments = get_leading_comments(self.test_copyright_sampl['android_copyright_v2'])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is True

    def test_is_copyright_correct__third_party_copyright__correct_3(self):
        comments = get_leading_comments(self.test_copyright_sampl['android_copyright_v3'])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is True

    def test_is_copyright_correct__third_party_copyright__incorrect(self):
        comments = get_leading_comments(self.test_copyright_sampl['android_bad_copyright'])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is False

    def test_is_copyright_correct__intel_copyright__correct(self):
        comments = get_leading_comments(self.test_copyright_sampl["intel_actual_copyright_v1"])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is True

    def test_is_copyright_correct__intel_copyright__correct_2(self):
        comments = get_leading_comments(self.test_copyright_sampl["intel_actual_copyright_v2"])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is True

    def test_is_copyright_correct__intel_copyright__correct_3(self):
        comments = get_leading_comments(self.test_copyright_sampl["intel_actual_copyright_v3"])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is True

    def test_is_copyright_correct__intel_copyright__incorrect(self):
        comments = get_leading_comments(self.test_copyright_sampl["intel_bad_copyright_v1"])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is False

    def test_is_copyright_correct__intel_copyright__incorrect_v2(self):
        comments = get_leading_comments(self.test_copyright_sampl["intel_bad_copyright_v2"])
        ret = self.copyright_checker.is_copyright_correct(comments)
        assert ret is False
