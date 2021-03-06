#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2011-2012, Michael Carroll
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of the copyright holders nor the names of any
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import bonjour

import sys
import socket
import zipfile
import os
import threading
import time
import logging

from layout import Layout

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class LayoutHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/touchosc')
            self.send_header('Content-Disposition',
                             'attachment; filename="%s.touchosc"' % self.server.layoutName)
            self.end_headers()
            self.wfile.write(self.server.layoutContents)
        except Exception:
            import traceback
            traceback.print_exc(f=sys.stdout)   
        return
    
    def log_message(self, *args):
        self.server.log_message(*args)
        
    def log_error(self, *args):
        self.server.log_error(*args)

class StoppableHTTPServer(HTTPServer):
    stopped = False
    def __init__(self, log_message, log_error, layoutName, layoutContents, *args):
        self.log_message = log_message
        self.log_error = log_error
        self.layoutName = layoutName
        self.layoutContents = layoutContents
        HTTPServer.__init__(self,*args)
    
    def serve_forever(self):
        while not self.stopped:
            self.handle_request()
            
    def server_close(self):
        HTTPServer.server_close(self)
        self.stopped = True
        
    def shutdown(self):
        pass

class LayoutServer(object):
    def __init__(self, layout, name, port, debug = None, info = None, error = None):
        """
        LayoutServer - IO class for sending TouchOSC layouts to iPhones and iPads.
        
        @type layoutPath: str
        @param layoutPath: Path to the TouchOSC file to be hosted.
        @type name: str
        @param name: Name of the OSC server as seen by iPhone/iPad
        @type port: int
        @param port: Port number to host the layout file on. 
        """
        self.debug = logging.debug
        self.info = logging.info
        self.error = logging.error
        
        if debug:
            self.debug = debug
        if error:
            self.error = error
        if info:
            self.info = info

        self.layout = layout
        layoutName = str(layout)
        layoutContents = layout.toXml()

        self.bonjourServer = bonjour.Bonjour(name, port,
                                             '_touchosceditor._tcp',
                                             debug = self.debug,
                                             info = self.info,
                                             error = self.error)
        
        self.httpd = StoppableHTTPServer(self.debug,
                                         self.error,
                                         layoutName,
                                         layoutContents,
                                         ('', port),
                                         LayoutHTTPRequestHandler)

    def run(self):
        self.bonjourServer.run_register()
        self.t = threading.Thread(target=self._run_http)
        self.t.daemon = True
        self.t.start()
    
    def stop(self):
        self.bonjourServer.stop_register()
        self.httpd.shutdown()
        self.httpd.server_close()
        
    def _run_http(self, ):
        try:
            self.httpd.serve_forever()
        except:
            pass

    @classmethod
    def createFromExisting(cls, source, name, port, debug=None, info=None, error=None):
        """
        Create a TouchOSC LayoutServer from an existing TouchOSC Layout file.

        @type source: filename or fileobject
        @param source: Path to an existing .touchosc file, or
            TouchOSC index.xml file (from unzipping .touchosc file)
        @rtype: Layout
        @return: An instance containing the layout
        """
        layout = Layout.createFromExisting(source)

        return LayoutServer(layout, name, port, debug, info, error)


def main(argv, stdout):
    usage = "usage: %prog [options] /path/to/layout.touchosc"
    parser = OptionParser(usage=usage)
    parser.add_option("-p", "--port", action="store", type="int", dest="port",
            default=9658,
            help="Port that the layout server will host on.")
    parser.add_option("-n", "--name", action="store", type="string", dest="name",
            default="OSC Layout Server on %s" % socket.gethostname(),
            help="Name that will appear in TouchOSC's Server List")
    parser.add_option("--log", action="store", dest="logging",
                      help="Set logging level", default = "INFO")
    (options, args) = parser.parse_args(argv)
    if len(args) < 2:
        parser.error("Please specify a layout file.")
        sys.exit(1)
    layoutFilePath = args[1]
    
    if options.logging:
        numeric_level = options.logging.upper()
    else:
        numeric_level = None
    logging.basicConfig(level=numeric_level)
    
    # Attempt to instantiate the server class.  Returns a ValueError if the
    # layoutFilePath is incorrect    
    try:
        server = LayoutServer.createFromExisting(layoutFilePath, options.name, options.port)
    except ValueError as e:
        parser.error(e.message)
        sys.exit(1)
    
    # Run the server and stop it on a keyboard interrupt.
    try:
        server.run()
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()

if __name__ == '__main__':
    from optparse import OptionParser
    main(sys.argv, sys.stdout)
