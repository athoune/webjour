#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Lecarme <mathieu@garambrogne.net>"

import os
import glob
import plistlib
import shutil

FOLDER = 'static/icons/'

def icns_to_png(target, dest):
	for size in ['16x16', '128x128', '512x512']:
		print os.popen("icns2png -x %s -s %s -o %s" % (target, size, dest)).read()
def application(name):
	if name.startswith("/"):
		folder = "%s.app/Contents" % name
	else:
		folder = "/Applications/%s.app/Contents" %name
	plist = plistlib.readPlist("%s/Info.plist" % folder)
	#CFBundleIdentifier
	tmp = '/tmp/%s.icns' % plist['CFBundleIdentifier']
	icon = plist['CFBundleIconFile']
	if not icon.endswith('.icns'):
		icon = "%s.icns" % icon
	shutil.copyfile("%s/Resources/%s" % (folder, icon), tmp)
	icns_to_png(tmp, FOLDER)
	#os.rmdir(tmp)

def computers():
	folders = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources"
	for computer in glob.glob('%s/com.apple.*' % folders):
		print computer
		icns_to_png(computer, FOLDER)

applications = ['iPhoto', 'iTunes', 'Safari', 'Utilities/Terminal', '/System/Library/CoreServices/Screen Sharing', '/System/Library/CoreServices/Finder', '/Developer/Applications/Xcode']

computers()
for app in applications:
	print app
	application(app)