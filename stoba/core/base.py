# -*- coding: utf-8 -*-
#
#
# This file is a part of 'django-stoba' project.
#
# Copyright (c) 2016, Vassim Shahir
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software without
#    specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import unicode_literals, absolute_import

from django.core.cache import cache
from django.core.files.storage import Storage
from binascii import crc32

class Cachable(object):
    
    def _generate_cachable_key(self,key):
        return 'STOBA_{:x}'.format(crc32(key) & 0xffffffff)
    
    def add_content(self, key, value):
        cache.add(self._generate_cachable_key(key),value,None)
    
    def get_content(self,key):
        return cache.get(self._generate_cachable_key(key))
        
    def del_content(self,key):
        cache.delete(self._generate_cachable_key(key))
        
    def __init__(self,content=None):
        if isinstance(content, dict):
            map(lambda x: self.add_content(*x), content.items())
    
    def __setitem__(self, key, value):
        self.add_content(key, value)
    
    def __getitem__(self, key):
        return self.get_content(key)
    
    def __delitem__(self, key):
        self.del_content(key)
    
    def __getattr__(self, key):
        return self.get_content(key)
         
    def __delattr__(self, key):
        if key not in vars(self):
            self.del_content(key)
        else:
            return super(Cachable,self).__delattr__(key)
         
    def __setattr__(self, key, value):
        if key not in vars(self):
            self.add_content(key, value)
        else:
            return super(Cachable,self).__setattr__(key, value)
        

class BaseStorage(Storage):
    
    cachable = Cachable()