from troposphere import (
    Template,
    GetAtt,
    Output,
    Parameter,
    Ref,
    Sub,
    securityhub,
    config,
    iam
)


from awacs.aws import (
    PolicyDocument,
    Statement,
    Allow,
    Principal
)
import awacs.sts


template = Template(
    Description='Central SecurityHub to aggregate to'
)


# hub = template.add_resource(
#     securityhub.Hub(
#         'CloudPlatformSecurityHub'
#     )
# )


aggregator_role = template.add_resource(
    iam.Role(
        'AggregatorRole',
        AssumeRolePolicyDocument=PolicyDocument(
            Statement=[
                Statement(
                    Effect=Allow,
                    Principal=Principal('Service', 'config.amazonaws.com'),
                    Action=[awacs.sts.AssumeRole]
                )
            ]
        ),
        Path='/service-role/',
        ManagedPolicyArns=[
            'arn:aws:iam::aws:policy/service-role/AWSConfigRoleForOrganizations'
        ]
    )
)

aggregator = template.add_resource(
    config.ConfigurationAggregator(
        'CloudPlatformConfigAggregator',
        ConfigurationAggregatorName='CloudPlatformConfigAggregator',
        OrganizationAggregationSource=config.OrganizationAggregationSource(
            AwsRegions=['ap-southeast-2'],
            RoleArn=GetAtt(aggregator_role, 'Arn')
        )
    )
)

# template.add_output(
#     Output(
#         "CloudPlatformSecurityHubArn",
#         Description="ARN of CloudPlatform Security Hub",
#         Value=Ref(hub),
#     ),
# )


