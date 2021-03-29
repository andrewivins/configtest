#!/usr/bin/env python3

import asyncio
import aioboto3

import config
import run



def log(context, results, criteria, status):
    account_name = context['account']['Name']
    if account_name not in results:
        results[account_name] = {}
    assert criteria not in results[account_name]
    results[account_name][criteria] = status


async def main():
    session = aioboto3.Session()
    ou = config.hub.ou
    role = config.hub.iam_role

    results = {}


    async for context in run.account_iterator(session, ou, role):
        acct_sess = context['session']

        async with acct_sess.client('securityhub') as sechub:
            try:
                await sechub.describe_hub()
                hub_enabled = True
            except sechub.exceptions.InvalidAccessException:
                hub_enabled = False
            log(context, results, 'Security Hub enabled', hub_enabled)

        async with acct_sess.client('config') as confserv:
            response = await confserv.describe_config_rules()
            count = len(response['ConfigRules'])
            log(context, results, 'Has config rules', count > 0)

            response = await confserv.describe_configuration_aggregators()
            count = len(response['ConfigurationAggregators'])
            log(context, results, 'Has config aggregators', count > 0)

    for account, info in sorted(results.items(), key=lambda x: x[0]):
        for criteria, status in info.items():
            print(f'{account}: {criteria}: {status}')


if __name__ == '__main__':
    asyncio.run(main())