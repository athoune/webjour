#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Lecarme <mathieu@garambrogne.net>"

import os, glob

def icns_to_png(target, size, dest):
	print os.popen("icns2png -x %s -s %s -o %s" % (target, size, dest)).read()

def computers():
	folders = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources"
	for computer in glob.glob('%s/com.apple.*' % folders):
		print computer
		for size in ['16x16', '128x128', '512x512']:
			icns_to_png(computer, size, 'static/icons/')

computers()