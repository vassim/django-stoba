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

from django.utils.http import http_date, urlunquote, urlparse
from django.utils.six import PY3
from requests.auth import AuthBase
from collections import OrderedDict
from .helper import hmac_sha1, base_64

__author__ = 'Vassim Shahir'
__license__ = 'BSD 3-Clause License'
__copyright__ = 'Copyright 2016 Vassim Shahir'

AWS_DOMAIN = 'amazonaws.com'

REGION_ENDPOINT_MAP = {
    "us-east-1": "s3",
    "us-west-1": "s3-us-west-1",
    "us-west-2": "s3-us-west-2",
    "eu-west-1": "s3-eu-west-1",
    "eu-central-1": "s3.eu-central-1",
    "ap-northeast-1": "s3-ap-northeast-1",
    "ap-northeast-2": "s3.ap-northeast-2",
    "ap-southeast-1": "s3-ap-southeast-1",
    "ap-southeast-2": "s3-ap-southeast-2",
    "sa-east-1": "s3-sa-east-1"
}

def get_s3_endpoint(region,bucket=None):
    endpoint = [REGION_ENDPOINT_MAP[region],AWS_DOMAIN]
    if bucket is not None:
        endpoint.insert(0, bucket)
    return '.'.join(endpoint)


class S3Signature(object):
    
    def __init__(self, url, region, http_method, http_headers, creds, non_amz_headers_to_sign):
        self.http_method = http_method
        self.access_key_id, self.secret_access_key = creds
        
        parsed_url = urlparse(url)
        self.http_request_uri = parsed_url.path
        self.bucket = parsed_url.netloc.replace(get_s3_endpoint(region),'')[:-1]
        self.non_amz_headers, self.amz_headers = self._get_headers_for_sign(http_headers, non_amz_headers_to_sign)
        
    def get_signature(self):
        string_to_sign = self._get_string_to_sign()
        return base_64(hmac_sha1(self.secret_access_key.encode('utf-8'),string_to_sign))
    
    def _get_headers_for_sign(self,headers, required_non_amz_headers):
        
        non_amz_headers = OrderedDict([(init_header,'') for init_header in required_non_amz_headers])
        amz_headers = OrderedDict()
        
        for header in headers:
            if header in required_non_amz_headers:
                non_amz_headers[header] = headers[header].strip()
            elif header.startswith('X-Amz-'):
                amz_headers[header.lower()] = headers[header].strip()
                
        print 
        return (non_amz_headers, amz_headers)
        
    
    def _get_string_to_sign(self):
        result = [self.http_method, '\n']
        result.extend(["%s\n" % self.non_amz_headers[header] for header in self.non_amz_headers])
        result.extend([self._get_canonicalized_amz_headers(), self._get_canonicalized_resource()])
        return ''.join(result)
    
    def _get_canonicalized_amz_headers(self):
        if self.amz_headers:
            headers = sorted(self.amz_headers)
            result = ['{}:{}\n'.format(header, self.amz_headers[header]) for header in headers]
            return ''.join(result)
        else:
            return ''
    
    def _get_canonicalized_resource(self):
        return ''.join(["/", self.bucket, self.http_request_uri])
    

class S3Auth(AuthBase):
    
    NON_AMZ_HEADERS_TO_SIGN = ('Content-MD5', 'Content-Type', 'Date')
    
    def __init__(self, access_key_id, secret_access_key, region):
        self.access_key_id = str(access_key_id)
        self.secret_access_key = str(secret_access_key)
        self.region = region
        
    def __call__(self, r):
        # Create date header if it is not created yet.
        if 'Date' not in r.headers and 'X-Amz-Date' not in r.headers:
            r.headers[b'X-Amz-Date'] = http_date()
        
        signature = S3Signature(
            url = r.url, 
            http_headers = r.headers, 
            http_method = r.method,
            region = self.region,
            creds = (self.access_key_id,self.secret_access_key),
            non_amz_headers_to_sign = self.NON_AMZ_HEADERS_TO_SIGN
        )
        
        authorization_string = 'AWS %s:%s' % (self.access_key_id, signature.get_signature())
        r.headers[b'Authorization'] = authorization_string.encode('utf-8')
        
        return r