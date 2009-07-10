#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Lecarme <mathieu@garambrogne.net>"

#http://www.simonwheatley.co.uk/2008/04/06/avahi-finder-icons/

from wsgiref.simple_server import make_server
from wsgiref.util import setup_testing_defaults, request_uri
import threading
from urlparse import urlparse
import select
import socket
import sys
import httplib
import os.path
try:
	import simplejson as json
except ImportError:
	import json

import pybonjour

regtypes = ["_http._tcp.", "_https._tcp.", 
	"_daap._tcp.", #iTunes
	"_rfb._tcp.", #Screenshare
	"_dpap._tcp.", #iPhoto
	"_distcc._tcp.", #distributed compilation
	"_raop._tcp.", #airTunes
	"_afpoverctp._tcp.", #file sharing
	"_ssh._tcp.", #remote access
	"_device-info._tcp.",
	"_ipp._tcp.", #printer
	"_smb._tcp.", #windows share
	"_webdav._tcp.",
	"_webdavs._tcp."]
timeout = 5
resolved = []
queried = []
services = {}
ips = {}

def service_to_url(service):
	services = {'rfb':'vnc', 'afpoverctp':'afp'}
	if service in services:
		return services[service]
	return service

def clean_bonjour_name(bjr):
	return '.'.join(bjr.split('.')[:-4]).replace('\\032', ' ').replace('\\','')

def snapshot():
	global services
	global ips
	snapshots = []
	for key, value in services.iteritems():
		print ips
		if value['hosttarget'].endswith('.local.') and value['hosttarget'] in ips:
			host = ips[value['hosttarget']]
		else:
			host = value['hosttarget']
		service = value['fullname'].split('.')[-4][1:]
		snapshots.append({
			'service':service,
			'scheme' : service_to_url(service),
			'host'   : host,
			'port'   : value['port'],
			'name'   : clean_bonjour_name(value['fullname']),
		})
	return snapshots

def status(code):
	return "%i %s" % (code, httplib.responses[code])
	
MIME = {
	'jpg' : 'image/jpg',
	'png' : 'image/png',
	'css' : 'text/css',
	'js'  : 'application/x-javascript',
	'html': 'text/html'
}

class StopThread(threading.Thread):
	"""
	A thread wich can be stopped
	"""
	def __init__(self, name="Webjour"):
		self._stopevent = threading.Event()
		threading.Thread.__init__(self, name = name)
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

web = WebJour()
web.start()

def query_record_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
						  rrtype, rrclass, rdata, ttl):
	if errorCode == pybonjour.kDNSServiceErr_NoError:
		print '	 IP			=', socket.inet_ntoa(rdata)
		global ips
		ips[fullname] = socket.inet_ntoa(rdata)
		queried.append(True)

def resolve_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
					 hosttarget, port, txtRecord):
	if errorCode != pybonjour.kDNSServiceErr_NoError:
		return
	print 'Resolved service:'
	print '	 fullname	=', fullname
	print '	 hosttarget =', hosttarget
	print '	 port		=', port
	global services
	services[fullname] = {"fullname":fullname, "hosttarget":hosttarget, "port":port, "txtRecord":txtRecord}
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
		print 'Service removed %' % serviceName
		return
	print 'Service added; resolving'
	resolve_sdRef = pybonjour.DNSServiceResolve(
		0,
		interfaceIndex,
		serviceName,
		regtype,
		replyDomain,
		resolve_callback)
	try:
		while not resolved:
			ready = select.select([resolve_sdRef], [], [], timeout)
			if resolve_sdRef not in ready[0]:
				print 'Resolve timed out'
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

browsers = []
for regtype in regtypes:
	browse_sdRef= pybonjour.DNSServiceBrowse(
		regtype = regtype,
		callBack = browse_callback)
	browseT = BrowseThread(regtype, browse_sdRef)
	browsers.append(browseT)
	browseT.start()
	print "%s browsing" % regtype
try:
	while True:
		pass
except KeyboardInterrupt:
	print "Stop!"
	web.join()
	for b in browsers:
		b.join()
	sys.exit()

#browse_sdRef.close()
