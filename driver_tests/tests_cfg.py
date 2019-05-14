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

TESTS = {
    # decode
    # avc decode
    'CABA1_SVA_B': {
        "feature": "decode",
        "cmd": [
            "ffmpeg",
            "-hwaccel", "vaapi",
            "-hwaccel_device", "/dev/dri/renderD128",
            "-v", "verbose",
            "-i", "content/avc/CABA1_SVA_B.264",
            "-pix_fmt", "yuv420p",
            "-f", "rawvideo",
            "-vsync", "passthrough",
            "-vframes", "17",
            "-y", "temp/CABA1_SVA_B/CABA1_SVA_B.yuv"
        ],
        "ref_type": "psnr",
        "ref_value": "30"
    },
    'CABA1_Sony_D': {
        "feature": "decode",
        "cmd": [
            "ffmpeg",
            "-hwaccel", "vaapi",
            "-hwaccel_device", "/dev/dri/renderD128",
            "-v", "verbose",
            "-i", "content/avc/CABA1_Sony_D.jsv",
            "-pix_fmt", "yuv420p",
            "-f", "rawvideo",
            "-vsync", "passthrough",
            "-vframes", "50",
            "-y", "temp/CABA1_Sony_D/CABA1_Sony_D.yuv",
        ],
        "ref_type": "psnr",
        "ref_value": "30"
    },
    # encode
    # avc encode
    'avc_cbr_001': {
        "feature": "encode",
        "cmd": [
            "ffmpeg",
            "-hwaccel", "vaapi",
            "-vaapi_device",
            "/dev/dri/renderD128",
            "-v", "verbose",
            "-f", "rawvideo",
            "-pix_fmt", "yuv420p",
            "-s:v", "176x144",
            "-r:v", "30",
            "-i", "content/yuv/CABA1_SVA_B.yuv",
            "-vf", "format=nv12,hwupload",
            "-c:v", "h264_vaapi",
            "-profile:v", "main",
            "-g", "30",
            "-bf", "2",
            "-slices", "1",
            "-b:v", "500k",
            "-maxrate", "500k",
            "-vframes", "17",
            "-y", "temp/avc_cbr_001/CABA1_SVA_B.264"
        ],
        "ref_type": "psnr",
        "ref_value": "30"
    },
    "avc_cqp_001": {
        "feature": "encode",
        "cmd": [
            "ffmpeg",
            "-hwaccel", "vaapi",
            "-vaapi_device", "/dev/dri/renderD128",
            "-v", "verbose",
            "-f", "rawvideo",
            "-pix_fmt", "yuv420p",
            "-s:v", "176x144",
            "-i", "content/yuv/CABA1_SVA_B.yuv",
            "-vf", "format=nv12,hwupload",
            "-c:v", "h264_vaapi",
            "-profile:v", "high",
            "-g", "30",
            "-qp", "28",
            "-bf", "2",
            "-quality", "4",
            "-slices", "1",
            "-vframes", "17",
            "-y", "temp/avc_cqp_001/CABA1_SVA_B.264"
        ],
        "ref_type": "psnr",
        "ref_value": "30"
    },
    # vpp
    # vpp scale
    "scale_001": {
        "feature": "vp",
        "cmd": [
            "ffmpeg",
            "-hwaccel", "vaapi",
            "-vaapi_device", "/dev/dri/renderD128",
            "-v", "debug",
            "-f", "rawvideo",
            "-pix_fmt", "nv12",
            "-s:v", "176x144",
            "-i", "content/yuv/CABA1_SVA_B.yuv",
            "-vf", "format=nv12,hwupload,scale_vaapi=w=88:h=72,hwdownload,format=nv12",
            "-pix_fmt",
            "nv12",
            "-vframes", "27",
            "-y", "temp/scale_001/CABA1_SVA_B_88x72.yuv"
        ],
        "ref_type": "psnr",
        "ref_value": "28"
    }
}
