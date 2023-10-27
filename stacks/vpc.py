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

from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    Stack,
)

from constructs import Construct


class VpcStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        #create VPC
        self.vpc = ec2.Vpc(
            self,
            id="VPC",
            cidr="10.0.0.0/16",
            max_azs=2,
            nat_gateways=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public", cidr_mask=24,
                    reserved=False, subnet_type=ec2.SubnetType.PUBLIC),
                ec2.SubnetConfiguration(
                    name="private", cidr_mask=24,
                    reserved=False, subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetConfiguration(
                    name="DB", cidr_mask=24,
                    reserved=False, subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
                ),
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
            nat_gateway_provider=ec2.NatProvider.gateway(),
            nat_gateway_subnets=ec2.SubnetSelection(
                one_per_az=True,
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            gateway_endpoints={
                "S3": ec2.GatewayVpcEndpointOptions(
                    service=ec2.GatewayVpcEndpointAwsService.S3,
                ),
            },
        )
        cdk.Tag(key="Application", value=self.stack_name).visit(self.vpc)

        #create a vpc endpoint for secretsmanager
        self.vpc_endpoint = ec2.InterfaceVpcEndpoint(
            self,
            'VpcEndpointSecretsManager', 
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER, 
            open=True, 
            vpc=self.vpc
            )
        
        
        #create EC2 jumphost for dbeaver 
        self.instance_name = 'mbsjumphost'
        self.instance_type = 't2.micro'
        self.ami_name = 'al2023-ami-2023.0.20230614.0-kernel-6.1-x86_64'

        ami_image = ec2.MachineImage().lookup(name=self.ami_name)
        if not ami_image:
            print ('Failed finding AMI image')
            return

        instance_type = ec2.InstanceType(self.instance_type)
        if not instance_type:
            print ('Failed finding instance')
            return

        sec_grp= ec2.SecurityGroup(self, 'mbs-jump-host-ec2-sec-grp', vpc=self.vpc, allow_all_outbound=True)
        if not sec_grp:
            print ('Failed finding security group')
            return

        cdk.CfnOutput(
            self,
            id="VPCId",
            value=self.vpc.vpc_id,
            description="VPC ID",
            export_name=f"{self.region}:{self.account}:{self.stack_name}:vpc-id"
        )
        