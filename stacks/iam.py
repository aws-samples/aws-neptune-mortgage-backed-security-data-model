# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import aws_cdk as cdk
import boto3

from aws_cdk import (
    Stack,
    aws_iam as iam,
)

from constructs import Construct

class IamStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        role_name='dms-vpc-role'

        #Check if dms-vpc-role exists, if not create the role
        try:
            client = boto3.client('iam')
            response = client.get_role(RoleName=role_name)
        except:
            self.dms_vpc_role = iam.Role(self,
                "dms-vpc-role",
                role_name=role_name,
                assumed_by = iam.ServicePrincipal('dms.amazonaws.com'),
                managed_policies = [
                    iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AmazonDMSVPCManagementRole')
                ]
            )



