#!/usr/bin/env python

import os
import re
import hashlib
import sys
import collections
import multiprocessing

IMAGE_SUFFIXES = ["\\.gif", "\\.jpg", "\\.jpeg", "\\.png", "\\.bmp"]

class HashedImages(object):
  def __init__(self, max_threads=None):
    self._max_threads_ = max_threads
    self._pool = multiprocessing.Pool(self._max_threads)
    self._lock = threading.Lock()
    self._images = collections.defaultdict(list)

  def AddImage(filename):
    def AddAsync():
      hash, filename = hash_and_name(filename)
      with self._lock:
        self._images[hash].append(filename)
    self._pool.apply_async(AddAsync)

  def GetImages():
    self._pool.close()
    self._pool.join()
    return self._images

def has_image_filename(filename, allowed_suffixes):
  for suffix in allowed_suffixes:
    expr = ".*" + suffix + '$'
    if re.match(expr, filename, re.IGNORECASE):
      return True
  return False

def hash_and_name(filename):
  m = hashlib.sha256()
  m.update(open(filename).read())
  return [m.hexdigest(), filename]

def add_files(directory, allowed_suffixes):
  files = os.listdir(directory)
  directories_to_process = []
  images_with_hashes = []
  for filename in files:
    if filename == "." or filename == "..":
      continue
    fname = directory + "/" + filename
    if os.path.isdir(fname):
      directories_to_process.append(fname)
    if has_image_filename(fname, allowed_suffixes):
      images_with_hashes.append(hash_and_name(fname))

  for directory in directories_to_process:
    images_with_hashes.extend(add_files(directory, allowed_suffixes))
  return images_with_hashes

def find_dupes(hash_and_file_list):
  all = collections.defaultdict(list)
  for hash, filename in hash_and_file_list:
    all[hash].append(filename)
  only_dupes = {}
  for hash, lst in all.iteritems():
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
  files = []
  for dir in dir_names:
    files.extend(add_files(dir, IMAGE_SUFFIXES))
  dupes = find_dupes(files)
  handle_dupe_list(dupes)

if __name__ == "__main__":
  sys.exit(main())
