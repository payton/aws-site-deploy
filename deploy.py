import boto3
from botocore.exceptions import ClientError
import time


def main():
    print('------------AWS Site Deploy------------\n')
    region = input('Enter region: ')
    route_53(region)


def route_53(region):
    client = boto3.client('route53', region_name=region)
    domain_name = input('Enter domain name: ')

    hosted_zones = client.list_hosted_zones_by_name(
        DNSName=domain_name,
        MaxItems='1'
    )

    print('\nChoose existing Hosted Zone or create:\n')
    for i in range(len(hosted_zones['HostedZones'])):
        print(
            '\t{}) {} - {}'.format(i + 1, hosted_zones['HostedZones'][i]['Id'], hosted_zones['HostedZones'][i]['Name']))
    print('\t{}) Create Hosted Zone'.format(len(hosted_zones['HostedZones']) + 1))

    selection = input('\nEnter selection: ')

    while True:
        if selection == '2':
            hosted_zone = route_53_create_hosted_zone(client, domain_name)
            break
        elif selection == '1':
            hosted_zone = hosted_zones['HostedZones'][int(selection) - 1]
            break
        else:
            print('Invalid input.')

    certificate_manager(region, hosted_zone, domain_name)


def route_53_create_hosted_zone(client, domain_name):
    response = client.create_hosted_zone(
        Name=domain_name
    )
    return response['HostedZone']


def certificate_manager(region, hosted_zone, domain_name):
    client = boto3.client('acm', region_name='us-east-1')

    print('\nValidation methods to create certificate:\n')
    print('\t1) Email\n\t2) DNS')
    validation_method = input('\nEnter method: ')

    while True:
        if validation_method == '1':
            validation_method = 'EMAIL'
            break
        elif validation_method == '2':
            validation_method = 'DNS'
            break
        else:
            print('Invalid input.')

    certificate = client.request_certificate(
        DomainName=domain_name,
        ValidationMethod=validation_method,
        SubjectAlternativeNames=[
            '*.{}'.format(domain_name),
        ],
        IdempotencyToken=str(int(time.time()))
    )

    cloudformation(region, hosted_zone['Id'], certificate, domain_name)


def cloudformation(region, hosted_zone_id, certificate_arn, domain_name):
    client = boto3.client('s3', region_name=region)
    while True:
        try:
            client.get_bucket_policy(Bucket=domain_name)
            break
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                input('Conflicting bucket. Delete "{}" S3 bucket and press enter once done'.format(domain_name))

    with open('./template.json', 'r') as file:
        data = file.read().replace('\n', '')

    print(client.create_stack(
        StackName=domain_name,
        TemplateBody=data,
        Parameters=[
            {
                'ParameterKey': 'HostedZoneID',
                'ParameterValue': hosted_zone_id
            },
            {
                'ParameterKey': 'ACMCertificateARN',
                'ParameterValue': certificate_arn
            },
            {
                'ParameterKey': 'WebsiteURL',
                'ParameterValue': domain_name
            }
        ],
        DisableRollback=False,
        TimeoutInMinutes=60,
        Capabilities=[
            'CAPABILITY_IAM',
        ],
        OnFailure='ROLLBACK'
    ))

main()
