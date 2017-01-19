#!/usr/bin/env python

import threading
import os
import re
import hashlib
import sys
import collections
import multiprocessing
import time

IMAGE_SUFFIXES = ["\\.gif", "\\.jpg", "\\.jpeg", "\\.png", "\\.bmp"]

USE_PARALLEL_HASHING = True

class HashedImages(object):
  def __init__(self, max_threads=None):
    self._max_threads = max_threads
    self._pool = multiprocessing.Pool(self._max_threads)
    self._lock = threading.Lock()
    self._images = collections.defaultdict(list)
    self._first_image_added = None

  def _AddImageCallback(self, result):
    hash, filename = result
    with self._lock:
      self._images[hash].append(filename)

  def AddImage(self, filename):
    if self._first_image_added is None:
      self._first_image_added = time.time()
    if not USE_PARALLEL_HASHING:
      self._AddImageCallback(hash_and_name(filename))
    else:
      self._pool.apply_async(hash_and_name, args=(filename,),
                             callback=self._AddImageCallback)

  def GetImages(self):
    print "Waiting on hashing to complete."
    self._pool.close()
    self._pool.join()
    print "Hashing complete."
    print "Time to find files and hash them: %s" % (
        time.time() - self._first_image_added)
    return self._images


def has_image_filename(filename):
  for suffix in IMAGE_SUFFIXES:
    expr = ".*" + suffix + '$'
    if re.match(expr, filename, re.IGNORECASE):
      return True
  return False

def hash_and_name(filename):
  m = hashlib.sha256()
  m.update(open(filename).read())
  return [m.hexdigest(), filename]

def add_files(directory, hashes):
  files = os.listdir(directory)
  directories_to_process = []
  for filename in files:
    if filename == "." or filename == "..":
      continue
    fname = directory + "/" + filename
    if os.path.isdir(fname):
      directories_to_process.append(fname)
    if has_image_filename(fname):
      hashes.AddImage(fname)

  for directory in directories_to_process:
    add_files(directory, hashes)

def find_dupes(hash_and_file_list):
  only_dupes = {}
  for hash, lst in hash_and_file_list.iteritems():
    if len(lst) > 1:
      only_dupes[hash] = lst
  return only_dupes

def keep_which_dupe(hash, files):
  print "Matching hash: \n   %s" % hash
  print "Keep which file?"
  print "[0] All of them (don't delete)"
  cnt = 0
  for i, file in enumerate(files):
    print "[%s] %s" % (i + 1, file)
  print "> ",
  input = sys.stdin.readline()
  input = int(input[:-1])
  if input < 0 or input > len(files):
    print "Invalid Input\n"
    return keep_which_dupe(hash, files)
  if input == 0:
    return
  input -= 1
  for i, file in enumerate(files):
    if i == input:
      continue
    os.remove(file)

def handle_dupe_list(dupes):
  cnt = 0
  total = len(dupes)
  for hash, files in dupes.iteritems():
    cnt += 1
    print "Match %s of %s" % (cnt, total)
    keep_which_dupe(hash, files)

def main(argv=None):
  if argv is None:
    argv = sys.argv
  dir_names = ['.']
  if len(argv) >= 2:
    dir_names = argv[1:]
  hashes = HashedImages()
  for dir in dir_names:
    add_files(dir, hashes)
  dupes = find_dupes(hashes.GetImages())
  handle_dupe_list(dupes)

if __name__ == "__main__":
  sys.exit(main())
