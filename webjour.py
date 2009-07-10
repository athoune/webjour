#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Mathieu Lecarme <mathieu@garambrogne.net>"

from wsgiref.simple_server import make_server
from wsgiref.util import setup_testing_defaults
import threading

import select
import socket
import sys
import pybonjour

regtype	 = "_http._tcp."#sys.argv[1]
timeout	 = 5
resolved = []
queried = []
services = {}

class WebJour(threading.Thread):
	def web(self, environ, start_response):
		setup_testing_defaults(environ)

		status = '200 OK'
		headers = [('Content-type', 'text/plain')]

		start_response(status, headers)

		#ret = ["%s: %s\n" % (key, value)
	  #         for key, value in environ.iteritems()]
		global services
		print services
		return [("%s => %s:%i\n" % (key, value['hosttarget'], value['port'])).encode('utf8')
	           for key, value in services.iteritems()]

	def run(self):
		httpd = make_server('', 8000, self.web)
		print "Serving on port 8000..."
		httpd.serve_forever()

web = WebJour()
web.start()

def query_record_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
						  rrtype, rrclass, rdata, ttl):
	if errorCode == pybonjour.kDNSServiceErr_NoError:
		print '	 IP			=', socket.inet_ntoa(rdata)
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

	query_sdRef = \
		pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex,
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
		print 'Service removed'
		return

	print 'Service added; resolving'

	resolve_sdRef = pybonjour.DNSServiceResolve(0,
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


browse_sdRef = pybonjour.DNSServiceBrowse(regtype = regtype,
										  callBack = browse_callback)

try:
	try:
		while True:
			ready = select.select([browse_sdRef], [], [])
			if browse_sdRef in ready[0]:
				pybonjour.DNSServiceProcessResult(browse_sdRef)
	except KeyboardInterrupt:
		pass
finally:
	browse_sdRef.close()
