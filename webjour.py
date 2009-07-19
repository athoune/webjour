#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Lecarme <mathieu@garambrogne.net>"

#http://www.simonwheatley.co.uk/2008/04/06/avahi-finder-icons/
#http://developer.apple.com/networking/bonjour/faq.html

from wsgiref.simple_server import make_server
from wsgiref.util import setup_testing_defaults, request_uri
import threading
from urlparse import urlparse
import select
import socket
import sys
import httplib
import os.path
import time

try:
	import simplejson as json
except ImportError:
	import json

import pybonjour

class ServiceType(object):
	def __init__(self, type, name, icon = None):
		self.type = type
		self.name = name
		self.icon = icon
	def __repr__(self):
		return "<service %s>" % self.type

regtypes = [
	ServiceType("_http._tcp.", "Web", 'com.apple.Safari'),
	ServiceType("_https._tcp.", "Secure web", 'com.apple.Safari'),
	ServiceType("_daap._tcp.", "iTunes", 'com.apple.iTunes'),
	ServiceType("_rfb._tcp.", "Screen share", 'com.apple.ScreenSharing'), #Screenshare
	ServiceType("_dpap._tcp.", "iPhoto", 'com.apple.iPhoto'), #iPhoto
	ServiceType("_distcc._tcp.", "Distributed computing", 'com.apple.Xcode'), #distributed compilation
	ServiceType("_raop._tcp.", "airTunes"), #airTunes
	ServiceType("_afpoverctp._tcp.", "Apple sharing", 'com.apple.Finder'), #file sharing
	ServiceType("_ssh._tcp.", "Secure shell", 'com.apple.Terminal'), #remote access
	ServiceType("_device-info._tcp.", "Device infos"),
	ServiceType("_ipp._tcp.", "Printer"), #printer
	ServiceType("_smb._tcp.", "Windows share"), #windows share
	ServiceType("_presence._tcp.", "Presence", "com.apple.iChat"),
	ServiceType("_webdav._tcp.", "Webdav"),
	ServiceType("_webdavs._tcp.", "Secire webdav"),
	ServiceType("_bittorrent._tcp.", "Bitorrent"),
	ServiceType("_sftp-ssh._tcp.", "SSH share", 'com.apple.Terminal')
	]
typeDico = {}
for regtype in regtypes:
	typeDico[regtype.type] = regtype
MIME = {
		'jpg' : 'image/jpg',
		'png' : 'image/png',
		'css' : 'text/css',
		'js'  : 'application/x-javascript',
		'html': 'text/html'
	}

timeout = 5
resolved = []
queried = []
services = {}
ips = {}
service_infos = {}

def service_to_url(service):
	services = {
		'rfb':'vnc',
		'afpoverctp':'afp',
		'presence':'xmpp',
		'sftp-ssh':'sftp'
	}
	if service in services:
		return services[service]
	return service

def clean_bonjour_name(bjr):
	return '.'.join(bjr.split('.')[:-4]).replace('\\032', ' ').replace('\\','')

def snapshot():
	global services
	global ips
	global typeDico
	snapshots = []
	keys = services.keys()
	keys.sort()
	for key in keys:
		value = services[key]
		print ips
		if value['hosttarget'].endswith('.local.') and value['hosttarget'] in ips:
			host = list(ips[value['hosttarget']])
		else:
			host = [value['hosttarget']]
		host.sort()
		service = value['fullname'].split('.')[-4][1:]
		type = '.'.join(value['fullname'].split('.')[-4:-2]) + '.'
		snapshots.append({
			'service'  : service,
			'scheme'   : service_to_url(service),
			'host'     : host,
			'port'     : value['port'],
			'name'     : clean_bonjour_name(value['fullname']),
			'desc'     : typeDico[type].name,
			'icon'     : typeDico[type].icon,
			'txtRecord': value['txtRecord']
		})
	return snapshots

def parseText(data):
	txt = {}
	while data:
		length = ord(data[0])
		item = data[1:length+1].split('=', 1)
		if item[0] and (item[0] not in txt):
			if len(item) == 1:
				txt[item[0]] = None
			else:
				txt[item[0]] = item[1]
		data = data[length+1:]
	return txt

def status(code):
	return "%i %s" % (code, httplib.responses[code])
	
class StopThread(threading.Thread):
	"""
	A thread wich can be stopped
	"""
	def __init__(self, name="Webjour"):
		self._stopevent = threading.Event()
		threading.Thread.__init__(self, name = name)
		self.daemon = True
	def join(self, timeout=None):
		self._stopevent.set()
		threading.Thread.join(self,timeout)

class WebJour(StopThread):
	def web(self, environ, start_response):
		setup_testing_defaults(environ)
		url = urlparse(request_uri(environ))
		headers = []
		if url.path == '/webjour':
			headers.append(('Content-type', MIME['js']))
			start_response(status(httplib.OK), headers)
			return [json.dumps(snapshot())]
		if url.path == '/':
			path = 'static/index.html'
		else:
			path = 'static%s' % url.path
		if os.path.isfile(path):
			headers.append(('Content-type', MIME[path.split('.')[-1]]))
			start_response(status(httplib.OK), headers)
			return [open(path,'rb').read()]
		start_response(status(httplib.NOT_FOUND), headers)
		#ret = ["%s: %s\n" % (key, value)
	  #         for key, value in environ.iteritems()]
		
		#return [("%s => %s:%i\n" % (key, value['hosttarget'], value['port'])).encode('utf8')
	    #       for key, value in services.iteritems()]
	def run(self):
		httpd = make_server('', 8000, self.web)
		print "Serving on port 8000..."
		while not self._stopevent.isSet():
			httpd.handle_request()

def query_record_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
						  rrtype, rrclass, rdata, ttl):
	if errorCode == pybonjour.kDNSServiceErr_NoError:
		print '	 IP de %s = %s' %  (fullname, socket.inet_ntoa(rdata))
		global ips
		if fullname not in ips:
			ips[fullname] = set()
		ips[fullname].add(socket.inet_ntoa(rdata))
		queried.append(True)

def resolve_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
					 hosttarget, port, txtRecord):
	if errorCode != pybonjour.kDNSServiceErr_NoError:
		return
	print 'Resolved service:'
	print '	 fullname	=', fullname
	print '	 hosttarget =', hosttarget
	print '	 port		=', port
	print '	txt		=', parseText(txtRecord)
	global services
	services[fullname] = {"fullname":fullname, "hosttarget":hosttarget, "port":port, "txtRecord":parseText(txtRecord)}
	query_sdRef = pybonjour.DNSServiceQueryRecord(
		interfaceIndex = interfaceIndex,
		fullname = hosttarget,
		rrtype = pybonjour.kDNSServiceType_A,
		callBack = query_record_callback)
	try:
		while not queried:
			ready = select.select([query_sdRef], [], [], timeout)
			if query_sdRef not in ready[0]:
				print 'Query record timed out'
				break
			pybonjour.DNSServiceProcessResult(query_sdRef)
		else:
			queried.pop()
	finally:
		query_sdRef.close()
	resolved.append(True)

def browse_callback(sdRef, flags, interfaceIndex, errorCode, serviceName,
					regtype, replyDomain):
	if errorCode != pybonjour.kDNSServiceErr_NoError:
		return
	if not (flags & pybonjour.kDNSServiceFlagsAdd):
		print 'Service removed %s' % serviceName
		print interfaceIndex, regtype, replyDomain
		return
	print 'Service added; resolving'
	for resolve_sdRef in [pybonjour.DNSServiceResolve(
		0,
		interfaceIndex,
		serviceName,
		regtype,
		replyDomain,
		resolve_callback), 
		#pybonjour.DNSServiceResolve(
		#	0,
		#	interfaceIndex,
		#	"_device-info._tcp.",
		#	regtype,
		#	replyDomain,
		#	resolve_callback)
		]:
		try:
			while not resolved:
				ready = select.select([resolve_sdRef], [], [], timeout)
				if resolve_sdRef not in ready[0]:
					print 'Resolve timed out :', serviceName
					break
				pybonjour.DNSServiceProcessResult(resolve_sdRef)
			else:
				resolved.pop()
		finally:
			resolve_sdRef.close()

class BrowseThread(StopThread):
	def __init__(self, name, browse_sdRef):
		self.browse_sdRef = browse_sdRef
		StopThread.__init__(self, name)
	def run(self):
		while not self._stopevent.isSet():
			ready = select.select([self.browse_sdRef], [], [])
			if self.browse_sdRef in ready[0]:
				pybonjour.DNSServiceProcessResult(self.browse_sdRef)

web = WebJour()
browsers = []

try:
	web.start()
	for regtype in regtypes:
		browse_sdRef= pybonjour.DNSServiceBrowse(
			regtype = regtype.type,
			callBack = browse_callback)
		browseT = BrowseThread(regtype, browse_sdRef)
		browsers.append(browseT)
		browseT.start()
		print "%s browsing" % regtype
	while True:
		time.sleep(15)
except KeyboardInterrupt:
	print "Stop!"
	web.join(15)
	for b in browsers:
		print "%s is stopping" % b.name
		b.join(15)

#browse_sdRef.close()
