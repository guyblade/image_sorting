#!/usr/bin/env python

import argparse

import SocketServer
import SimpleXMLRPCServer
import threading
import time
import re
import BaseHTTPServer
import sys
import os
import urllib
import duplicate_image_check
import shutil

def die(message):
  raise Exception(message)

def PrettySize(size):
  if size < 1024:
    return "%s B" % size
  if size < 1024 * 1024:
    return "%s KB" % (int(size * 100 / 1024) / 100.0)
  return "%s MB" % (int(size * 100 / (1024 * 1024)) / 100.0)

def Composer(base, proxied_functions):
  class Composed(base):
    def __init__(self, other):
      self._proxy = other

    def __getattr__(self, attr):
      print "looking for %s" % attr
      if attr in proxied_functions:
        return self._proxy.__dict__[attr]
      if attr not in self.__dict__ and hasattr(self._proxy, attr):
        return getattr(self._proxy, attr)
      if attr in self.__dict__:
        return self.__dict__[attr]
      raise AttributeError()


  return Composed

def HandlerProxy(dispatchers):
  class HandlerProxyInternal(BaseHTTPServer.BaseHTTPRequestHandler):
    FUNCTIONS_TO_PROXY = ['setup', 'handle', 'finish']

    def pick_proxy(self):
      proxier = dispatchers['/']
      for prefix, proxy_class in dispatchers.iteritems():
        if prefix == '/':
          continue
        if self.path.startswith(prefix + '/'):
          self.path = self.path[len(prefix):]
          proxier = proxy_class
          break
      return Composer(proxier, self.FUNCTIONS_TO_PROXY)

    def do_proxy(self, method):
      proxy_class = self.pick_proxy()
      r = proxy_class(self)
      return getattr(r, 'do_' + method)()

    def do_GET(self):
      return self.do_proxy('GET')

    def do_POST(self):
      return self.do_proxy('POST')

    def do_PUT(self):
      return self.do_proxy('PUT')

  return HandlerProxyInternal

def ImgServer(image_directory):
  class ImgServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
      if self.path.find("..") != -1:
        return self.send_error(404, "Nice try")
      image_file = image_directory + urllib.unquote(self.path).decode('utf8')
      if not os.path.isfile(image_file):
        return self.send_error(404, "No such file")
      self.send_response(200)
      self.send_header("Content-type", "img/png")
      self.end_headers()
      data = open(image_file).read()
      self.wfile.write(data)
      print "Served [size %s] %s" % (PrettySize(len(data)), image_file)
      return

  return ImgServerHandler

def image_list(directory):
  files = os.listdir(directory)
  ret = []
  for file in files:
    if duplicate_image_check.has_image_filename(file):
      ret.append(file)
  ret.sort()
  return ret

def RootServer(image_directory):
  class RootServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
      if self.path == "/" or self.path == "index.html":
        return self.index()
      return self.send_error(404, "Nice try")


    def index(self):
      self.send_response(200)
      self.send_header("Content-type", "text/html")
      self.end_headers()
      w = self.wfile.write
      w("<html><head>")
      w("<title>%s</title>" % image_directory)
      w("<link rel='stylesheet' type='text/css' href='res/is.css'>")
      w('<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.1.1/jquery.min.js"></script>')
      w('<script src="res/jquery-xmlrpc.js"></script>')
      w("<script language='javascript' src='res/everything.js'></script>")
      w("</head>")
      w("<body><div id='controls'></div><img id='main_image' class='preview' /><div id='notes'></div></body>")
      w("</html>")

  return RootServerHandler

def ResourceServer(files_to_serve):
  class ResourceServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
      if self.path in files_to_serve.iterkeys():
        return self.serve_file(self.path)
      if self.path[0] == '/' and self.path[1:] in files_to_serve.iterkeys():
        return self.serve_file(self.path[1:])

    def serve_file(self, file):
      if not os.path.isfile(file):
        return self.send_error(404, "No such file")
      self.send_response(200)
      self.send_header("Content-type", files_to_serve[file])
      self.end_headers()
      self.wfile.write(open(file).read())

  return ResourceServerHandler

def RpcServer(dispatcher):
  class Handler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    def do_POST(self):
      self.server = dispatcher
      SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.do_POST(self)

  return Handler

def RemoveImage(browse_dir, filename, dry_run):
  full_name = brwose_dir + '/' + filename
  if not os.path.isfile(full_name):
    return False
  if dry_run:
    print "Would remove [%s]" % full_name
    return True
  os.unlink(full_name)

def MoveImage(browse_dir, save_dir, filename, dry_run):
  full_source = browse_dir + '/' + filename
  full_dest = save_dir + '/' + filename
  print "Got request to move [%s] to [%s]" % (full_source, full_dest)
  if not os.path.isfile(full_source):
    print "Tried to move invalid file?"
    return False
  if os.path.isfile(full_dest):
    print "Tried to move file to a destination that is already in use!"
    return False
  if dry_run:
    print "Would move [%s] to [%s]" % (full_source, full_dest)
    return True
  try:
    shutil.copyfile(full_source, full_dest)
    return True
  except:
    return False

def GetImageList(browse_dir):
  return image_list(browse_dir)

class Server(SocketServer.ThreadingMixIn,
             BaseHTTPServer.HTTPServer):
  def __init__(self, port, browse_directory, save_directory, dry_run):
    self._browse_dir = browse_directory
    self._save_dir = save_directory
    self._dry_run = dry_run
    resources = {
        'is.css': 'text/css',
        'everything.js': 'text/javascript',
        'jquery-xmlrpc.js': 'text/javascript'
    }
    self._dispatcher = SimpleXMLRPCServer.SimpleXMLRPCDispatcher()
    self.SetUpRpcServer()
    handlers = {'/img': ImgServer(self._browse_dir),
                '/res': ResourceServer(resources),
                '/': RootServer(self._browse_dir),
                '/rpc': RpcServer(self._dispatcher)}
    BaseHTTPServer.HTTPServer.__init__(self, ('', port), HandlerProxy(handlers))

  def SetUpRpcServer(self):
    def RemoveImageL(filename):
      return RemoveImage(self._browse_dir, filename, self._dry_run)
    def MoveImageL(filename):
      print "Got move image request: [%s]" % filename
      return MoveImage(self._browse_dir, self._save_dir, filename, self._dry_run)
    def ImageList():
      print "Got image list request"
      return GetImageList(self._browse_dir)

    self.logRequests = True
    self._dispatcher.logRequests = self.logRequests
    self._send_traceback_header = True
    self._dispatcher._send_traceback_header = self._send_traceback_header
    self._dispatcher.register_function(RemoveImageL, 'RemoveImage')
    self._dispatcher.register_function(MoveImageL, 'MoveImage')
    self._dispatcher.register_function(ImageList)


def read_args():
  args = argparse.ArgumentParser(
      description='Start a webserver to sort through images')
  args.add_argument('--browse_directory', dest='browse_directory',
                    type=unicode, required=True)
  args.add_argument('--save_directory', dest='save_directory',
                    type=unicode, required=True)
  args.add_argument('--port', dest='port', type=int, default=8088,
                    required=False)
  args.add_argument('--dryrun', dest='dryrun', action='store_true');
  args.add_argument('--no-dryrun', dest='dryrun', action='store_false');
  args.set_defaults(dryrun=True)
  return args.parse_args()


def main():
  args = read_args()
  if args.port < 1024 or args.port >= 65535:
    die("Port number must be between 1024 and 65535")
  s = Server(args.port, args.browse_directory, args.save_directory, args.dryrun)
  s.serve_forever()


if __name__ == "__main__":
  sys.exit(main())
