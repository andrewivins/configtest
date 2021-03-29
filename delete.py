#!/usr/bin/env python3

import asyncio
import aioboto3
from botocore.exceptions import ClientError

import config
import run



async def delete(session, config):
    stack_name = config.stack_name
    async with session.client('cloudformation') as cfn:
        await cfn.delete_stack(StackName=stack_name)

async def undelegate_admin_account(session, account_id):
    async with session.client('securityhub') as sechub:
        try:

            await sechub.disable_organization_admin_account(
                AdminAccountId=account_id
            )
            print(f'Disabled security hub admin delegation for {account_id}')
        except Exception as e:
            print(f'Could not disable security hub admin delegation for {account_id}: {e}')


async def disable_security_hub(session):
    async with session.client('securityhub') as sechub:
        try:
            await sechub.disable_security_hub()
            print('Disabled security hub for account')
        except Exception as e:
            print(f'Could not disable security hub: {e}')


async def main():
    session = aioboto3.Session()

    security_account = config.hub.security_account_name

    ou = config.config.ou
    role = config.config.iam_role

    # # Config rules
    async for context in run.account_iterator(session, ou, role):
        stack_name = config.config.stack_name
        account_name = context['account']['Name']
        print(f'Deleting {stack_name} from {account_name}')
        await delete(context['session'], config.config)

    # await disable_security_hub(session)

    # SecurityHub
    # ou = config.hub.ou
    # role = config.hub.iam_role
    # async for context in run.account_iterator(session, ou, role, include=[security_account]):
    #     account_id = context['account']['Id']
    #     await undelegate_admin_account(session, account_id)
    #     stack_name = config.hub.stack_name
    #     account_name = context['account']['Name']
    #     print(f'Deleting {stack_name} from {account_name}')
    #     await delete(context['session'], config.hub) 
    #     await disable_security_hub(context['session'])

        

    




if __name__ == '__main__':
    asyncio.run(main())