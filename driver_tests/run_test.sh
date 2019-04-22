#!/bin/bash

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

INFO()
{
    echo -e "\e[32;1m[INFO] \e[0m$@"
}

ERROR()
{
    echo -e "\e[31;1m[ERROR] \e[0m$@"
}

env_check()
{
    lsmod | grep -q i915 && INFO "i915 load successfully" || ERROR "system does not load i915 module"
    if hash vainfo 2>/dev/null;then
        driverVersion=`vainfo 2>&1 | awk -F: '/Driver version/{print $NF}'`
        INFO "Driver version: $driverVersion"
        if echo $driverVersion | grep -q iHD;then
            INFO "Current media driver is iHD and supports gen11+ and Whiskylake platform"
        elif echo $driverVersion | grep -q i965;then
            INFO "Current media driver is i965 and supports pre-gen11 platform"
        fi
    fi
}

check_psnr() #$1 reference value,$2 inputfile, $3 outputfile name, $4 width, $5 height
{
    local refvalue=$1
    local inputFile=$2
    local outputFile=$3
    local width=$4
    local height=$5
    local outputYuv=$outputfile.yuv
    [ ! -s $outputfile ] && psnr='nan' && echo -e "reference psnr: $refvalue\nactual psnr:$psnr" && return -1
    vframes=`echo $cmdline | sed 's/^.*-vframes *\([[:graph:]]\+\).*$/\1/'`
    case $codecType in
        decode)
            echo "Decode the input file with ffmpeg sw"
            swOutputFile=${outputFile}_sw.yuv
            ffmpeg_sw_cmdline="`echo $cmdline | sed -e 's/-hwaccel [^ ]\+//' -e 's/-hwaccel_device [^ ]\+//'`_sw.yuv"
            echo "exec $ffmpeg_sw_cmdline"
            eval "$ffmpeg_sw_cmdline"
            cmp -s $outputFile $swOutputFile
            [ $? -eq 0 ] && INFO "md5 checksum is same with ffmpeg sw decode" && return 0
            width=`ffmpeg -i $inputFile 2>&1 | grep 'Stream #' | grep -o '[0-9]*x[0-9]*' | cut -dx -f1`
            height=`ffmpeg -i $inputFile 2>&1 | grep 'Stream #' | grep -o '[0-9]*x[0-9]*' | cut -dx -f2`
            psnr=`metrics_calc_lite -i1 $swOutputFile -i2 $outputFile -w $width -h $height psnr ssim all | awk '/<avg_metric=PSNR>/{print $2}' | cut -d'<' -f1`
            ;;
        encode)
            ffmpeg -v debug -i $outputFile -pix_fmt yuv420p -f rawvideo -vsync passthrough -vframes $vframes -y $outputYuv
            psnr=`metrics_calc_lite -i1 $inputFile -i2 $outputYuv -w $width -h $height psnr ssim all | awk '/<avg_metric=PSNR>/{print $2}' | cut -d'<' -f1`
            ;;
        vp)
            if echo "$cmdline" | grep -q scale_vaapi;then
                w=`echo $cmdline | sed 's/.*scale_vaapi=w=\([0-9]\+\).*/\1/'`
                h=`echo $cmdline | sed 's/.*scale_vaapi=w=[0-9]\+:h=\([0-9]\+\).*/\1/'`
                echo "Scale width = $w; height=$h"
                echo "do scaling with ffmpeg sw"
                swOutputFile=${outputFile}_sw.yuv
                sw_cmdline=$(echo $cmdline | sed -e 's/-hwaccel [^ ]\+//' -e 's/-vaapi_device [^ ]\+//' -e "s/-vf '[^']\+'/-vf 'scale=$w:$h'/")_sw.yuv
                eval "$sw_cmdline"
                cmp -s "$outputFile" "$swOutputFile"
                [ $? -eq 0 ] && echo "md5 checksum is same with ffmpeg sw decode" && return 0
                psnr=`metrics_calc_lite -i1 $swOutputFile -i2 $outputFile -w $w -h $h psnr ssim all | awk '/<avg_metric=PSNR>/{print $2}' | cut -d'<' -f1`
            fi
            ;;
    esac
    [ -z "$psnr" ] && return -1
    INFO "reference psnr: $refvalue"
    INFO "actual psnr: $psnr"
    psnr_gap=`echo | awk -v x=$refvalue -v y=$psnr '{print 100*(y-x)/x}'`
    INFO "psnr_gap: $psnr_gap%"
    [ `echo "$psnr_gap < -5" | bc` -eq 1 ]  && return -1 || return 0
}


check_md5() #$1 reference value,$2 outputfile name
{
   local refvalue=$1
   local outputfile=$2
   md5=`md5sum $outputfile | awk '{print $1}'`
   INFO  "reference md5: $refvalue"
   INFO  "actual md5: $md5"
   [ "$refvalue" = "$md5"  ] && return 0 || return -1
}

[ $# -ne 1 ] && echo "Usage: $0 <Test Id>" && exit 1
env_check
export DISPLAY=:0.0
export LD_LIBRARY_PATH=$PWD
#chmod a+x metrics_calc_lite
id=$1
cmdfile=commandline.csv
line=`grep -wm1 "^$id" $cmdfile`
[ -z "$line" ] && ERROR "Invalid Test Id" && exit 1
nf=`echo $line | awk -F, '{print NF}'`
codecType=`echo $line | cut -d, -f2`
cmdline=`echo $line | cut -d, -f3-$((nf-2))`
cmdline=`echo "$cmdline" | sed 's/\"//g'`
ref_type=`echo $line | awk -F, '{print $(NF-1)}'`
ref_value=`echo $line | awk -F, '{print $NF}'`
INFO "Test Id: $id"
INFO "Command-line: $cmdline"
inputFile=`echo $cmdline | sed 's/^.*-i *\([[:graph:]]\+\).*$/\1/'`
INFO "Input file: $inputFile"
if echo $cmdline | grep -q "\-s:v";then
    resolution=`echo $cmdline | sed 's/^.*s:v *\([[:graph:]]\+\).*$/\1/'`
    width=`echo $resolution | cut -dx -f1`
    height=`echo $resolution | cut -dx -f2`
    INFO "Width: $width"
    INFO "Height: $height"
fi
if [ $codecType != playback ];then
    outputfile=`echo $cmdline | awk '{print $NF}'`
    rm -rf $outputfile &>/dev/null
    mkdir -p ${outputfile%/*}
fi
eval $cmdline 2>&1 | tee log.txt
[ -z "$ref_value" ] && ref_value='no reference value'
case $ref_type in
    [mM][Dd]5)
        check_md5 "$ref_value" "$outputfile";;
    [pP][sS][nN][rR])
        check_psnr "$ref_value" "$inputFile" "$outputfile" "$width" "$height";;
    *)
        [ $codecType != playback ] && ERROR "Invaild reference type, only Support md5 and psnr" && exit
        grep -Eiqv 'FAIL|ERROR|INVALID' log.txt

esac
res=$?
echo '#########################################################################'
echo "Test Id: $id"
[ $res -eq 0 ] && echo -e "\e[32;1mTEST PASSED\e[0m" || echo -e "\e[31;1mTEST FAILED\e[0m"
echo '#########################################################################'
rm log.txt &>/dev/null
