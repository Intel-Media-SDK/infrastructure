OSV sanity test suite

Please run "./run_test.sh" to execute it. Here are the detail information for this suite.

1. Verify i915 driver is loaded or not
2. Check old(i965) or new(iHD) media driver in use
3. Run ffmpeg vaapi sanity test
    1. 2 cases for AVC Decode, compared with ffmpeg sw decode md5.
    2. 2 cases for AVC Encode(CQP and CBR), compared with original content by PSNR
    3. 1 case for Video Processing Scaling, compared with ffmpeg sw VP by PSNR

metrics_calc_lite is the tool to compare two yuv files. Usage:
metrics_calc_lite -i1 <contentfile_1> -i2 <contentfile_2> -w <content_width> -h <content_hight> psnr ssim all

Playback avc clip by ffplay example but it doesn't go through our driver.
ffplay  -autoexit -loop 1 content/avc/CABA1_Sony_D.jsv