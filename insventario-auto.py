import boto3
import json
import pandas as pd
import subprocess

lista_de_arquivos = []
 
class EC2Status:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('ec2')
        self.client_ssm_us_east_1 = self.session_us_east_1.client('ssm')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('ec2')
        self.client_ssm_sa_east_1 = self.session_sa_east_1.client('ssm')

    def get_status(self, client, client_ssm):
        instance_list = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        
        next_token = None
                
        while True:
            if next_token:
                response = client_ssm.describe_instance_information(NextToken=next_token)
            else:
                response = client_ssm.describe_instance_information()
                
            instance_list.extend(response['InstanceInformationList'])
            next_token = response.get('NextToken')
                
            if not next_token:
                break
                
        teste = []
                
        for instance in instance_list:
            instance_id = instance['InstanceId']
            ping_status = instance.get('PingStatus', 'Unknown')
            platform_type = instance.get('PlatformType', 'Unknown')
            os_type = instance.get('PlatformName', 'Unknown') + ' ' + instance.get('PlatformVersion', 'Unknown')
            teste.append({'Id': instance_id, 'PingStatus': ping_status, 'PlataformType': platform_type, 'OperationSystem': os_type})

        instances_status = []
        instances_info = client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'terminated']}])
        for reservation in instances_info['Reservations']:
            for instance in reservation['Instances']:
                image_id = instance['ImageId']
                instance_id = instance['InstanceId']
                instance_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'Name'), '-')
                ssm_installed = False
                for instance_info in teste:
                    if instance_info['Id'] == instance_id:
                        ssm_installed = True

                # Get AZ information
                availability_zone = instance['Placement']['AvailabilityZone']

                # Get attached volumes information
                volumes_info = []
                for volume in self.client_sa_east_1.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])['Volumes']:
                    volumes_info.append({'VolumeId': volume['VolumeId'], 'Type': volume['VolumeType'], 'Size (GiB)': volume['Size'], 'State': volume['State']})
                

                instance_type_info = self.client_sa_east_1.describe_instance_types(InstanceTypes=[instance['InstanceType']])['InstanceTypes'][0]
                instance_status = instance['State']['Name']
                platform_type = next((info['PlataformType'] for info in teste if info['Id'] == instance_id), 'Unknown')
                os_type = next((info['OperationSystem'] for info in teste if info['Id'] == instance_id), 'Unknown')
                
                instances_status.append({
                'InstanceId': instance_id,
                'ImageId': instance['ImageId'],
                'Account ID': account_id,
                'InstanceName': instance_name,
                'SSMAgentInstalled': ssm_installed,
                'Status': instance_status,
                'InstanceFamily': instance_type_info['InstanceType'],
                'vCPUs': instance_type_info['VCpuInfo']['DefaultVCpus'],
                'Memory (MiB)': instance_type_info['MemoryInfo']['SizeInMiB'],
                'AvailabilityZone': availability_zone,
                'PlataformType': platform_type,
                'OperationSystem': os_type,
                'Volumes': volumes_info
                })
                
        return instances_status

    def exec_ec2(self):
        ec2_us_east_1 = self.get_status(self.client_us_east_1, self.client_ssm_us_east_1)
        ec2_sa_east_1 = self.get_status(self.client_sa_east_1, self.client_ssm_sa_east_1)
        
        if ec2_sa_east_1:
            with open('/tmp/EC2 - SP.json', 'w') as f: 
                json.dump(ec2_sa_east_1, f, indent=4)
            lista_de_arquivos.append('EC2 - SP.json')
        
        if ec2_us_east_1:
            with open('/tmp/EC2 - NV.json', 'w') as f: 
                json.dump(ec2_us_east_1, f, indent=4)
            lista_de_arquivos.append('EC2 - NV.json') 
        
        return ec2_sa_east_1, ec2_us_east_1
        
class EBSVolumesStatus:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('ec2')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('ec2')

    def get_status(self, client):
        volumes_status = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        volumes_info = client.describe_volumes(Filters=[{'Name': 'status', 'Values': ['in-use', 'available']}])['Volumes']
        
        for volume in volumes_info:
            volume_id = volume['VolumeId']
            volume_name = next((tag['Value'] for tag in volume.get('Tags', []) if tag['Key'] == 'Name'), '-')
            volume_type = volume['VolumeType']
            volume_size = volume['Size']
            volume_state = volume['State']
            attached_instances = ', '.join([attachment['InstanceId'] for attachment in volume['Attachments']])
            volume_status = 'In Use' if volume['State'] == 'in-use' else 'Available'
            
            volumes_status.append({
                'VolumeName': volume_name,
                'VolumeId': volume_id,
                'Type': volume_type,
                'Size (GiB)': volume_size,
                'State': volume_state,
                'AttachedInstances': attached_instances,
                'Status': volume_status,
                'Account ID': account_id
            })
            
        total_size = sum([volume['Size (GiB)'] for volume in volumes_status])
        
        volumes_status.append({
            'VolumeName': 'Total',
            'Size (GiB)': total_size
        })
        
        return volumes_status
        
    def exec_ebs_volumes(self):
        ebs_us_east_1 = self.get_status(self.client_us_east_1)
        ebs_sa_east_1 = self.get_status(self.client_sa_east_1)
        
        if ebs_sa_east_1:
            with open('/tmp/EBS - SP.json', 'w') as f: 
                json.dump(ebs_sa_east_1, f, indent=4)
            lista_de_arquivos.append('EBS - SP.json')
        
        if ebs_us_east_1:
            with open('/tmp/EBS - NV.json', 'w') as f: 
                json.dump(ebs_us_east_1, f, indent=4)
            lista_de_arquivos.append('EBS - NV.json') 
        
        return ebs_sa_east_1, ebs_us_east_1

class EFSInfo:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('efs')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('efs')
    
    def get_efs_info(self, client):
        all_efs_info = []
        file_systems = client.describe_file_systems()
        account_id = boto3.client('sts').get_caller_identity()['Account']        
        for file_system in file_systems['FileSystems']:
            
            all_efs_info.append(
                {
                'Name': file_system['Name'],
                'FileSystemId': file_system['FileSystemId'],
                'SizeInBytes': file_system['SizeInBytes']['Value'],
                'LifeCycleState': file_system['LifeCycleState'],
                'AvailabilityZone': file_system['AvailabilityZoneName'],
                'Account ID': account_id
                }
                )
                
        return all_efs_info
    
    def save_to_json(self):
        efs_us_east_1 = self.get_efs_info(self.client_us_east_1)
        efs_sa_east_1 = self.get_efs_info(self.client_sa_east_1)

        if efs_sa_east_1:
            with open('/tmp/EFS - SP.json', 'w') as f: 
                json.dump(efs_sa_east_1, f, indent=4)
            lista_de_arquivos.append('EFS - SP.json')
        
        if efs_us_east_1:
            with open('/tmp/EFS - NV.json', 'w') as f: 
                json.dump(efs_us_east_1, f, indent=4)
            lista_de_arquivos.append('EFS - NV.json') 
        
        return efs_sa_east_1, efs_us_east_1
        
class FSXInfo:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('fsx')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('fsx')
    
    def get_fsx_info(self, client):
        all_fsx_info = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        volumes = client.describe_file_systems()
        
        for volume in volumes['FileSystems']:
            
            all_fsx_info.append(
                {
                'FileSystemId': volume['FileSystemId'],
                'OwnerId': volume['OwnerId'],
                'FileSystemType': volume['FileSystemType'],
                'Size': volume['StorageCapacity'],
                'StorageType': volume['StorageType'],
                'Lifecycle': volume['Lifecycle'],
                'Account ID': account_id
                }
                )
                
        return all_fsx_info
    
    def save_to_json(self):
        fsx_us_east_1 = self.get_fsx_info(self.client_us_east_1)
        fsx_sa_east_1 = self.get_fsx_info(self.client_sa_east_1)

        if fsx_sa_east_1:
            with open('/tmp/FSX - SP.json', 'w') as f: 
                json.dump(fsx_sa_east_1, f, indent=4)
            lista_de_arquivos.append('FSX - SP.json')
        
        if fsx_us_east_1:
            with open('/tmp/FSX - NV.json', 'w') as f: 
                json.dump(fsx_us_east_1, f, indent=4)
            lista_de_arquivos.append('FSX - NV.json') 
        
        return fsx_sa_east_1, fsx_us_east_1
  
class EKSInfo:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('ec2')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('ec2')
    
    def get_eks_info(self, client):
        all_eks_info = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        instances_info = client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'terminated']}, {'Name': 'tag-key', 'Values': ['eks:nodegroup-name', 'eks:cluster-name']}])
        for reservation in instances_info['Reservations']:
            for instance in reservation['Instances']:
                instance_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'Name'), '-')
                nodegroup_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'eks:nodegroup-name'), '-')
                cluster_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'eks:cluster-name'), None)
                availability_zone = instance['Placement']['AvailabilityZone']
                instance_type_info = self.client_sa_east_1.describe_instance_types(InstanceTypes=[instance['InstanceType']])['InstanceTypes'][0]
                
                if cluster_name:
                    all_eks_info.append({
                        'ClusterName': cluster_name,
                        'NodeGroupName': nodegroup_name,
                        'NodeName': instance_name,
                        'InstanceFamily': instance_type_info['InstanceType'],
                        'vCPUs': instance_type_info['VCpuInfo']['DefaultVCpus'],
                        'Memory (MiB)': instance_type_info['MemoryInfo']['SizeInMiB'],
                        'AvailabilityZone': availability_zone,
                        'Account ID': account_id
                        
                    })
                    
        return all_eks_info
    
    def save_to_json(self):
        eks_us_east_1 = self.get_eks_info(self.client_us_east_1)
        eks_sa_east_1 = self.get_eks_info(self.client_sa_east_1)

        if eks_us_east_1:
            with open('/tmp/EKS - NV.json', 'w') as f: 
                json.dump(eks_us_east_1, f, indent=4)
            lista_de_arquivos.append('EKS - NV.json') 
        
        if eks_sa_east_1:
            with open('/tmp/EKS - SP.json', 'w') as f: 
                json.dump(eks_sa_east_1, f, indent=4)
            lista_de_arquivos.append('EKS - SP.json')
        
        return eks_us_east_1, eks_sa_east_1


class RDSInfo:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('rds')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('rds')
    
    def get_rds_info(self, client):
        all_rds_info = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        instances = client.describe_db_instances()
        
        for instance in instances['DBInstances']:
            iops = instance.get('Iops')  # Verifica se 'Iops' existe no dicionário
            
            all_rds_info.append(
                {
                'DBInstanceIdentifier': instance['DBInstanceIdentifier'],
                'Engine': instance['Engine'],
                'EngineVersion': instance['EngineVersion'],
                'AvailabilityZone': instance['AvailabilityZone'],
                'AllocatedStorage': instance['AllocatedStorage'],
                'DBInstanceStatus': instance['DBInstanceStatus'],
                'DBInstanceType': instance.get('DBInstanceClass'),
                'Account ID': account_id,
                'Iops' : iops if iops else '-'  # Usa 'N/A' se 'Iops' não existe
                }
                )
                
        return all_rds_info
    
    def save_to_json(self):
        rds_us_east_1 = self.get_rds_info(self.client_us_east_1)
        rds_sa_east_1 = self.get_rds_info(self.client_sa_east_1)

        if rds_sa_east_1:
            with open('/tmp/RDS - SP.json', 'w') as f: 
                json.dump(rds_sa_east_1, f, indent=4)
            lista_de_arquivos.append('RDS - SP.json')
        
        if rds_us_east_1:
            with open('/tmp/RDS - NV.json', 'w') as f: 
                json.dump(rds_us_east_1, f, indent=4)
            lista_de_arquivos.append('RDS - NV.json') 
        
        return rds_sa_east_1, rds_us_east_1
        
class DocDb:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('docdb')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('docdb')
    
    def get_docdb_info(self, client):
        all_docdb_info = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        instances = client.describe_db_clusters()

        for instance in instances['DBClusters']: 
            cluster_identifier = instance['DBClusterIdentifier']
            for dbinstance in instance['DBClusterMembers']:
                name = dbinstance['DBInstanceIdentifier']

            all_docdb_info.append(
                {
                    'Cluster identifier': cluster_identifier,
                    'DBClusterMembers' : name,
                    'Status': instance['Status'],
                    'EngineVersion': instance['EngineVersion'],
                    'AvailabilityZones': instance['AvailabilityZones'],
                    'Account ID': account_id
                    }
            )

        return all_docdb_info
    
    def save_docdb_json(self):
        docdb_us_east_1 = self.get_docdb_info(self.client_us_east_1)
        docdb_sa_east_1 = self.get_docdb_info(self.client_sa_east_1)

        if docdb_sa_east_1:
            with open('/tmp/DocDB - SP.json', 'w') as f: 
                json.dump(docdb_sa_east_1, f, indent=4)
            lista_de_arquivos.append('DocDB - SP.json')
        
        if docdb_us_east_1:
            with open('/tmp/DocDB - NV.json', 'w') as f: 
                json.dump(docdb_us_east_1, f, indent=4)
            lista_de_arquivos.append('DocDB - NV.json') 
        
        return docdb_sa_east_1, docdb_us_east_1

        
class DynamoDB():
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('dynamodb')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('dynamodb')
    
    def get_table(self, client):
        tables_list = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        table_names = client.list_tables()['TableNames']
         
        for table_name in table_names:
                table = client.describe_table(TableName=table_name)['Table']
                read_capacity_mode = table['ProvisionedThroughput']['ReadCapacityUnits']
                write_capacity_mode = table['ProvisionedThroughput']['WriteCapacityUnits']
                try:
                    billing_mode = table['BillingModeSummary']['BillingMode']
                except KeyError:
                    billing_mode = 'UNKNOWN'
                read_capacity_mode = 'ondemand' if billing_mode == 'PAY_PER_REQUEST' else read_capacity_mode
                write_capacity_mode = 'ondemand' if billing_mode == 'PAY_PER_REQUEST' else write_capacity_mode
                total_size = table['TableSizeBytes']
                tables_list.append({
                    'TableName': table_name,
                    'Status': table['TableStatus'],
                    'ReadCapacityMode': read_capacity_mode,
                    'WriteCapacityMode': write_capacity_mode,
                    'TotalSize': total_size,
                    'Account ID': account_id
                    })
        return tables_list
        
    def save_tables(self):
        dynamo_us_east_1 = self.get_table(self.client_us_east_1)
        dynamo_sa_east_1 = self.get_table(self.client_sa_east_1)

        if dynamo_sa_east_1:
            with open('/tmp/Dynamo - SP.json', 'w') as f: 
                json.dump(dynamo_sa_east_1, f, indent=4)
            lista_de_arquivos.append('Dynamo - SP.json')
        
        if dynamo_us_east_1:
            with open('/tmp/dynamo - NV.json', 'w') as f: 
                json.dump(dynamo_us_east_1, f, indent=4)
            lista_de_arquivos.append('dynamo - NV.json') 
        
        return dynamo_sa_east_1, dynamo_us_east_1

class ApiGateWay:
    
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        self.session_us_east_1 = boto3.Session(region_name=region_name_us_east_1)
        self.client_us_east_1 = self.session_us_east_1.client('apigateway')

        self.session_sa_east_1 = boto3.Session(region_name=region_name_sa_east_1)
        self.client_sa_east_1 = self.session_sa_east_1.client('apigateway')
    
    def get_apigateway_info(self, client):
        all_apigateway_info = []
        account_id = boto3.client('sts').get_caller_identity()['Account']
        apis = client.get_rest_apis()
        
        for api in apis['items']: 
            
            all_apigateway_info.append(
                {
                    "name": api["name"],
                    "Id": api["id"],
                    'Account ID': account_id
                    }
            )
                
        return all_apigateway_info
    
    def save_apigateway_json(self):
        apigateway_us_east_1 = self.get_apigateway_info(self.client_us_east_1)
        apigateway_sa_east_1 = self.get_apigateway_info(self.client_sa_east_1)

        if apigateway_sa_east_1:
            with open('/tmp/ApiGW - SP.json', 'w') as f: 
                json.dump(apigateway_sa_east_1, f, indent=4)
            lista_de_arquivos.append('ApiGW - SP.json')
        
        if apigateway_us_east_1:
            with open('/tmp/ApiGW - NV.json', 'w') as f: 
                json.dump(apigateway_us_east_1, f, indent=4)
            lista_de_arquivos.append('ApiGW- NV.json') 
        
        return apigateway_sa_east_1, apigateway_us_east_1

def lambda_handler(event, context):
    
    ec2 = EC2Status()
    ec2.exec_ec2()
    
    eks = EKSInfo()
    eks.save_to_json() 
    
    efs = EFSInfo()
    efs.save_to_json()
    
    fsx = FSXInfo()
    fsx.save_to_json()
    
    ebs = EBSVolumesStatus()
    ebs.exec_ebs_volumes()
    
    rds = RDSInfo()
    rds.save_to_json()
    
    docdb = DocDb()
    docdb.save_docdb_json()
    
    dynamo = DynamoDB()
    dynamo.save_tables()
    
    apigw = ApiGateWay()
    apigw.save_apigateway_json()
     
    json_files = lista_de_arquivos

    # dicionário que armazenará cada arquivo JSON convertido em DataFrame
    data_frames = {}
    
    # converter cada arquivo JSON em um DataFrame e armazenar no dicionário
    for file in json_files:
        with open('/tmp/' + file, 'r') as f:
            data_frames[file] = pd.read_json(f)
    
    # criar um objeto ExcelWriter para salvar a planilha
    writer = pd.ExcelWriter('/tmp/resultados.xlsx', engine='xlsxwriter') 
    
    # salvar cada DataFrame como uma folha da planilha
    for name, data in data_frames.items():
        data.to_excel(writer, sheet_name=name.split('.')[0], index=False)
    
    # fechar o objeto ExcelWriter
    writer.save()
    
    s3 = boto3.client('s3')
    bucket_name = os.environ.get('BUCKET_S3')
    s3.upload_file('/tmp/resultados.xlsx', bucket_name, 'resultados.xlsx')
    
    return {
        'statusCode': 200, 
        'body': lista_de_arquivos
        }

