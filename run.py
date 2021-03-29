#!/usr/bin/env python3

import asyncio
import aioboto3
from botocore.exceptions import ClientError

import config


OU='root'
IAM_ROLE='AWSControlTowerExecution'



async def get_caller_identity(session):
    async with session.client('sts') as sts:
        return await sts.get_caller_identity()


async def get_calling_account_id(session):
    return (await get_caller_identity(session))['Account']


async def assume_role(session, account_id, iam_role):
    async with session.client('sts') as sts:
        role_arn = f'arn:aws:iam::{account_id}:role/{iam_role}'
        sts_creds = await sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=iam_role
        )
        return get_boto3_sts_session(
            sts_creds['Credentials']['AccessKeyId'],
            sts_creds['Credentials']['SecretAccessKey'],
            sts_creds['Credentials']['SessionToken']
        )

def get_boto3_sts_session(aws_access_key_id, aws_secret_access_key, aws_session_token):
    return aioboto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token
    )

async def account_iterator(session, ou=None, role=None, include=[], exclude=[]):
    calling_account = await get_calling_account_id(session)
    if ou == 'root':
        ou = None
    async with session.client('organizations') as orgs:
        if ou:
            accounts = (await orgs.list_accounts_for_parent(ParentId=ou))['Accounts']
        else:
            accounts = (await orgs.list_accounts())['Accounts']
        for account in accounts:
            if include and account['Name'] not in include:
                continue
            if exclude and account['Name'] in exclude:
                continue
            if account['Status'].lower() == 'active' and account['Id'] != calling_account:
                if role:
                    assumed_session = await assume_role(session, account['Id'], role)
                    print(f'Assumed role {role} for {account["Name"]}')
                yield dict(account=account, session=assumed_session)


async def assume_role_for_account(session, role, account_name):
    async with session.client('organizations') as orgs:
        accounts = (await orgs.list_accounts())['Accounts']
        for account in accounts:
            if account['Name'].lower() == account_name.lower():
                assumed_session = await assume_role(session, account['Id'], role)
                return dict(account=account, session=assumed_session)


async def describe_stack(session, stack_name):
    async with session.client('cloudformation') as cfn:
        response = await cfn.describe_stacks(
            StackName=stack_name
        )
        stack = response['Stacks'][0]
        return stack


async def create(session, config):
    template_body = config.get_template_body()
    stack_name = config.stack_name
    params = config.parameters.as_parameters()
    async with session.client('cloudformation') as cfn:
        await cfn.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=params,
            Capabilities=['CAPABILITY_IAM'],
        )



async def update(session, config):
    template_body = config.get_template_body()
    stack_name = config.stack_name
    params = config.parameters.as_parameters()
    async with session.client('cloudformation') as cfn:
        await cfn.update_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Parameters=params,
            Capabilities=['CAPABILITY_IAM'],
        )

async def deploy(session, config):
    stack_name = config.stack_name
    async with session.client('cloudformation') as cfn:
        try:
            stack = await describe_stack(session, stack_name)
            status = stack['StackStatus']
        except:
            status = None

        if not status:
            await create(session, config)
        else:
            try:
                await update(session, config)
            except:
                pass


async def delegate_admin_account(session, account_id):
    async with session.client('securityhub') as sechub:
        try:
            await sechub.enable_organization_admin_account(
                AdminAccountId=account_id
            )
            print(f'Enabled security hub admin delegation for {account_id}')
        except:
            print(f'Could not enable security hub admin delegation for {account_id} (already enabled?)')


async def enable_security_hub_auto(session):
    async with session.client('securityhub') as sechub:
        try:
            await sechub.update_organization_configuration(AutoEnable=True)
            print(f'Turned on SecurityHub AutoEnable for organization')
        except Exception as e:
            print(f'Could not turn on SecurityHub AutoEnable for the organization: {e} ')


async def invite_member_accounts(session):
    async with session.client('securityhub') as sechub:    
        members = await sechub.list_members(OnlyAssociated=False)
        account_ids = [dict(AccountId=member['AccountId']) for member in members['Members']]
        try:
            await sechub.create_members(AccountDetails=account_ids)
            print('Added all member accounts')
        except Exception as e:
            print(f'Some member accounts could not be associated: {e}')


async def enable_service_access(session, service):
    async with session.client('organizations') as orgs:
        try:
            await orgs.enable_aws_service_access(ServicePrincipal=f'{service}.amazonaws.com')
            print(f'Enabled AWS service access for {service}')
        except Exception as e:
            print(f'Failed to enable service access: {e}')


async def disable_service_access(session, service):
    async with session.client('organizations') as orgs:
        try:
            await orgs.disable_aws_service_access(ServicePrincipal=f'{service}.amazonaws.com')
            print(f'Disabled AWS service access for {service}')
        except Exception as e:
            print(f'Failed to disable service access: {e}')


async def register_delegated_admin(session, service, account_id):
    async with session.client('organizations') as orgs:
        try:
            await orgs.register_delegated_administrator(
                ServicePrincipal=f'{service}.amazonaws.com',
                AccountId=account_id
            )
            print(f'Delegated admin for {service} to {account_id}')
        except orgs.exceptions.AccountAlreadyRegisteredException:
            pass
        except Exception as e:
            print(f'Failed to delegate admin: {e}')

async def deregister_delegated_admin(session, service, account_id):
    async with session.client('organizations') as orgs:
        try:
            await orgs.deregister_delegated_administrator(
                ServicePrincipal=f'{service}.amazonaws.com',
                AccountId=account_id
            )
            print(f'Undelegated admin for {service} to {account_id}')
        except Exception as e:
            print(f'Failed to undelegate admin: {e}')



async def main():
    session = aioboto3.Session()

    security_account = config.hub.security_account_name

    # SecurityHub
    ou = config.hub.ou
    role = config.hub.iam_role

    context = await assume_role_for_account(session, role, security_account)

    await enable_service_access(session, 'config')
    await register_delegated_admin(session, 'config', context['account']['Id'])

    stack_name = config.hub.stack_name
    account_name = context['account']['Name']
    print(f'Deploying {stack_name} into {account_name}')
    await deploy(context['session'], config.hub) 

    # account_id = context['account']['Id']
    # await delegate_admin_account(session, account_id)
    # await enable_security_hub_auto(context['session'])
    # await invite_member_accounts(context['session'])
            


    # Config rules
    ou = config.config.ou
    role = config.config.iam_role
    async for context in account_iterator(session, ou, role, exclude=[security_account]):
        stack_name = config.config.stack_name
        account_name = context['account']['Name']
        print(f'Deploying {stack_name} into {account_name}')
        await deploy(context['session'], config.config) 




if __name__ == '__main__':
    asyncio.run(main())