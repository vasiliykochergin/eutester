# Software License Agreement (BSD License)
#
# Copyright (c) 2009-2011, Eucalyptus Systems, Inc.
# All rights reserved.
#
# Redistribution and use of this software in source and binary forms, with or
# without modification, are permitted provided that the following conditions
# are met:
#
#   Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
#   Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# Author: tony@eucalyptus.com

from eutester import Eutester
import re
import os
import copy
from boto.ec2.autoscale import AutoScaleConnection
import boto.ec2.autoscale
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
import boto.ec2.autoscale
from boto.ec2.regioninfo import RegionInfo
import boto

ASRegionData = {
    'us-east-1': 'autoscaling.us-east-1.amazonaws.com',
    'us-west-1': 'autoscaling.us-west-1.amazonaws.com',
    'us-west-2': 'autoscaling.us-west-2.amazonaws.com',
    'eu-west-1': 'autoscaling.eu-west-1.amazonaws.com',
    'ap-northeast-1': 'autoscaling.ap-northeast-1.amazonaws.com',
    'ap-southeast-1': 'autoscaling.ap-southeast-1.amazonaws.com',
    'ap-southeast-2': 'autoscaling.ap-southeast-2.amazonaws.com',
    'sa-east-1': 'autoscaling.sa-east-1.amazonaws.com'}


class ASops(Eutester):
    def __init__(self, host=None, credpath=None, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None,
                 username="root", region=None, is_secure=False, path='/', port=80, boto_debug=0):
        """
        :param host:
        :param credpath:
        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param username:
        :param region:
        :param is_secure:
        :param path:
        :param port:
        :param boto_debug:
        """
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.account_id = None
        self.user_id = None
        super(ASops, self).__init__(credpath=credpath)

        self.setup_as_connection(host=host,
                                 region=region,
                                 endpoint=endpoint,
                                 aws_access_key_id=self.aws_access_key_id,
                                 aws_secret_access_key=self.aws_secret_access_key,
                                 is_secure=is_secure,
                                 path=path,
                                 port=port,
                                 boto_debug=boto_debug)
        self.poll_count = 48
        self.username = username
        self.test_resources = {}
        self.setup_as_resource_trackers()

    def setup_as_connection(self, endpoint=None, aws_access_key_id=None, aws_secret_access_key=None, is_secure=True,
                            host=None, region=None, path="/", port=443, boto_debug=0):
        """
        :param endpoint:
        :param aws_access_key_id:
        :param aws_secret_access_key:
        :param is_secure:
        :param host:
        :param region:
        :param path:
        :param port:
        :param boto_debug:
        :raise:
        """
        as_region = RegionInfo()
        if region:
            self.debug("Check region: " + str(region))
            try:
                if not endpoint:
                    as_region.endpoint = ASRegionData[region]
                else:
                    as_region.endpoint = endpoint
            except KeyError:
                raise Exception('Unknown region: %s' % region)
        else:
            as_region.name = 'eucalyptus'
            if not host:
                if endpoint:
                    as_region.endpoint = endpoint
                else:
                    as_region.endpoint = self.get_as_ip()
        connection_args = {'aws_access_key_id': aws_access_key_id,
                           'aws_secret_access_key': aws_secret_access_key,
                           'is_secure': is_secure,
                           'debug': boto_debug,
                           'port': port,
                           'path': path,
                           'region': as_region}

        if re.search('2.6', boto.__version__):
            connection_args['validate_certs'] = False

        try:
            as_connection_args = copy.copy(connection_args)
            as_connection_args['path'] = path
            as_connection_args['region'] = as_region
            self.debug("Attempting to create auto scale connection to " + as_region.endpoint + ":" + str(port) + path)
            # self.AS = boto.connect_autoscale(**as_connection_args)
            self.AS = boto.ec2.autoscale.connect_to_region("eucalyptus", aws_access_key_id, aws_secret_access_key)
        except Exception, e:
            self.critical("Was unable to create auto scale connection because of exception: " + str(e))

        #Source ip on local test machine used to reach instances
        self.as_source_ip = None

    def setup_as_resource_trackers(self):
        """
        Setup keys in the test_resources hash in order to track artifacts created
        """
        self.test_resources["keypairs"] = []
        self.test_resources["security-groups"] = []
        self.test_resources["images"] = []

    def create_launch_config(self, name=None, image_id=None, key_name=None, security_groups=None):
        """
        Creates a new launch configuration with specified attributes.

        :param name: Name of the launch configuration to create. (Required)
        :param image_id: Unique ID of the Amazon Machine Image (AMI) assigned during registration. (Required)
        :param key_name: The name of the EC2 key pair.
        :param security_groups: Names of the security groups with which to associate the EC2 instances.
        """
        self.debug("*** LC name = " + name)
        self.debug("*** LC image = " + image_id)
        self.debug("*** LC key = " + key_name)
        self.debug("*** LC group = " + security_groups)

        lc = LaunchConfiguration(name=name,
                                 image_id=image_id,
                                 key_name=key_name,
                                 security_groups=security_groups)
        self.AS.create_launch_configuration(lc)

    def delete_launch_config(self, launch_config_name):
        self.AS.delete_launch_configuration(launch_config_name)

    def create_as_group(self, group_name=None, load_balancers=None, availability_zones=None, launch_config=None,
                        min_size=None, max_size=None, connection=None):
        """
        Create auto scaling group.

        :param group_name: Name of autoscaling group (required).
        :param load_balancers: List of load balancers.
        :param availability_zones: List of availability zones (required).
        :param launch_config: Name of launch configuration (required).
        :param min_size:  Minimum size of group (required).
        :param max_size: Maximum size of group (required).
        :param connection: connection to auto scaling service
        """
        as_group = AutoScalingGroup(group_name=group_name,
                                    load_balancers=load_balancers,
                                    availability_zones=availability_zones,
                                    launch_config=launch_config,
                                    min_size=min_size,
                                    max_size=max_size,
                                    connection=connection)
        self.AS.create_auto_scaling_group(as_group)