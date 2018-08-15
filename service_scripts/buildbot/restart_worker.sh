#!/bin/bash

sudo service buildbot-worker restart || sudo systemctl restart buildbot-worker
