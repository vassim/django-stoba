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

from django.core.files.base import File
from django.core.exceptions import ImproperlyConfigured
from django.utils.deconstruct import deconstructible
from django.utils.http import parse_http_date_safe, urlquote, urlencode
from django.conf import settings
from datetime import datetime, timedelta
from .base import CloudStorage
from ..auth.s3_auth import S3Auth, REGION_ENDPOINT_MAP, get_s3_endpoint, S3Signature
from ...core.helper import tz_aware_datetime, datetime_to_epoch
import requests
import xmltodict


__author__ = 'Vassim Shahir'
__license__ = 'BSD 3-Clause License'
__copyright__ = 'Copyright 2016 Vassim Shahir'


URL_EXPIRE_TIME_IN_SEC = 60 * 30 # 30 minutes

@deconstructible
class S3(CloudStorage):
    
    NON_AMZ_HEADERS_FOR_URL_GENERATION = ('Content-MD5', 'Content-Type', 'Expires')
    
    def __init__(self,options=None):
        
        self._settings = {
            'region': 'us-east-1',
            'access_key_id': None,
            'secret_access_key' : None,
            'bucket_name': None,
            'service_url':  None,
            'url_expires_in_sec': URL_EXPIRE_TIME_IN_SEC,
            'set_content_type_as': None
        }
        
        if isinstance(settings.STOBA_S3,dict):
            self._settings.update(settings.STOBA_S3)
        
        if isinstance(options,dict):
            self._settings.update(options)
        
        self._validate()
        
        self.service_url = "https://%s" % get_s3_endpoint(
            bucket = urlquote(self._settings['bucket_name']), 
            region = urlquote(self._settings['region'])
        )
        
        super(S3, self).__init__()
    
    def _validate(self):
        
        if self._settings['access_key_id'] is  None or \
                self._settings['bucket_name'] is  None or \
                self._settings['secret_access_key'] is  None:
            raise ImproperlyConfigured('You must properly configure access_key_id, secret_access_key and bucket_name')
        
        if self._settings['region'] not in REGION_ENDPOINT_MAP.keys():
            raise ImproperlyConfigured('You must provide a valid region')
    
    def _authenticate(self):
        return S3Auth(
            self._settings['access_key_id'], 
            self._settings['secret_access_key'],
            self._settings['region']
        )
        
    def _get_object_url(self, name):
        return "/".join((self.service_url, urlquote(self._get_path(name))))
    
    def _get_modified_date(self,name):
        parsed_date = parse_http_date_safe(self._get_object_status(name)['last-modified'])
        if parsed_date is not None:
            return tz_aware_datetime(datetime.fromtimestamp(parsed_date))
        else:
            return tz_aware_datetime(datetime.now())
         
    def _open(self, name, mode='rb'):
        response = requests.get(self._get_object_url(name),auth=self._authenticate(), stream=True)
        return File(response.raw, name)
    
    def _save(self, name, content):  
        file_content = File(content)
        
        requests.put(self._get_object_url(name),auth=self._authenticate(), data=file_content)
        self.cachable['{}_size'.format(name)] = file_content.size
        
        return name
    
    def _get_object_status(self,name):
        response = requests.head(self._get_object_url(name),auth=self._authenticate())
        
        result = { header.lower():response.headers[header] for header in response.headers}
        result['status'] = response.status_code
        
        return result
    
    def _get_file_size(self,name):
        if self.cachable['{}_size'.format(name)] is None:
            self.cachable['{}_size'.format(name)] = int(self._get_object_status(name)['content-length'])
        return self.cachable['{}_size'.format(name)]
    
    def _get_expire_timestamp(self):
        expires_on = datetime.now() + timedelta(seconds=self._settings['url_expires_in_sec'])
        return datetime_to_epoch(expires_on)
    
    def _get_presigned_url(self, name):
        expire_time = self._get_expire_timestamp()
        url_params = {
              'AWSAccessKeyId': self._settings['access_key_id'],
              'Expires':expire_time,
              'Signature':self._get_url_signature(name, expire_time)
        }
        url_data = urlencode(url_params)
        return ''.join((self._get_object_url(name),'?',url_data))
    
    def _get_url_signature(self, name, expire_time_epoch):
        s3_sig = S3Signature(
             url = self._get_object_url(name),
             region = self._settings['region'],
             http_method = 'GET',
             http_headers = {'Expires':expire_time_epoch},
             creds = (self._settings['access_key_id'],self._settings['secret_access_key']),
             non_amz_headers_to_sign = self.NON_AMZ_HEADERS_FOR_URL_GENERATION
        )
        return s3_sig.get_signature()
    
    def _unserialize_s3_response(self,data):
        return xmltodict.parse(data)
    
    def _get_dir_list(self,dir_name):
        
        #IMPROVE THE CODE HERE
        
        result = []
        dir_path = '%s/' % self._get_path(dir_name)
        response = requests.get(self.service_url, auth=self._authenticate(), params={'delimiter':'/','prefix':dir_path}, stream=True)
        data = self._unserialize_s3_response(response.raw)
        
        for s3_tag in ('Contents','Key'),('CommonPrefixes','Prefix'):
            try:
                contents = data['ListBucketResult'][s3_tag[0]]
                if isinstance(contents,list):
                    for content in contents:
                        result.append(content[s3_tag[1]])
                else:
                    result.append(contents[s3_tag[1]])
            except:
                pass
        try:
            result.remove(dir_path)
        except:
            pass
                
        return result
    
    
    def url(self, name):
        return self._get_presigned_url(name)
    
    def delete(self, name):
        requests.delete(self._get_object_url(name),auth=self._authenticate(), headers={'Content-Length':0})
        del self.cachable['{}_size'.format(name)]
        
    def size(self, name):
        return self._get_file_size(name)
    
    def exists(self, name):
        if self._get_object_status(name)['status'] == requests.codes.not_found:
            return False
        else:
            return True
        
    def modified_time(self, name):
        return self._get_modified_date(name)
        
    def created_time(self, name):
        return self._get_modified_date(name)
        
    def listdir(self, dir_name):
        return self._traverse_folder(self._get_dir_list(dir_name))