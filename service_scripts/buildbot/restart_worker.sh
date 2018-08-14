#!/bin/bash

sudo service buildbot-worker restart 2> /dev/null || sudo systemctl restart buildbot-worker