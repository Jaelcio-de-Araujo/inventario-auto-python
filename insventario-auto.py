import boto3
import json
import pandas as pd 
from datetime import date
import botocore 

lista_de_arquivos = []
 
class AWSInventario:
    def __init__(self, region_name_us_east_1='us-east-1', region_name_sa_east_1='sa-east-1'):
        ids = ['12345678901', '12345678902', '12345678903']
        sts = boto3.client('sts')
        self.regions = {}

        for id in ids:
            role_arn = f'arn:aws:iam::{id}:role/Inventario_role'
            assumed_role = sts.assume_role(RoleArn=role_arn, RoleSessionName='AssumedRoleSession')
            credentials = assumed_role['Credentials']
            access_key = credentials['AccessKeyId']
            secret_key = credentials['SecretAccessKey']
            session_token = credentials['SessionToken']
            role_id = str(id)
            

            self.regions[id] = {}
            for region_name in [region_name_us_east_1, region_name_sa_east_1]:
                session = boto3.Session(region_name=region_name, aws_access_key_id=access_key, aws_secret_access_key=secret_key, aws_session_token=session_token)
                client = session.client('ec2')
                client_efs = session.client('efs')
                client_fsx = session.client('fsx')
                client_ssm = session.client('ssm')
                client_rds = session.client('rds')
                client_doc_db = session.client('docdb')
                client_dynamodb = session.client('dynamodb')
                client_apigateway = session.client('apigateway')
                client_s3 = session.client('s3')
                self.regions[id][region_name] = {
                    'session': session, 
                    'client': client, 
                    'client_ssm': client_ssm, 
                    'client_efs': client_efs, 
                    'client_fsx': client_fsx,
                    'client_rds': client_rds,
                    'client_doc_db': client_doc_db,
                    'client_dynamodb': client_dynamodb,
                    'client_apigateway': client_apigateway,
                    'client_s3': client_s3 
                    }


    def get_status_ec2(self, region, role_id):
        client = region['client']
        client_ssm = region['client_ssm']
        
        instance_list = []
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
                ssm_installed = any(info['Id'] == instance_id for info in teste)
                
                # Get AZ information
                availability_zone = instance['Placement']['AvailabilityZone']
                
                # Get attached volumes information
                volumes_info = []
                
                for volume in client.describe_volumes(Filters=[{'Name': 'attachment.instance-id', 'Values': [instance_id]}])['Volumes']:
                    volumes_info.append({'VolumeId': volume['VolumeId'], 'Type': volume['VolumeType'], 'Size (GiB)': volume['Size'], 'State': volume['State']})
                
                instance_type_info = client.describe_instance_types(InstanceTypes=[instance['InstanceType']])['InstanceTypes'][0]
                instance_status = instance['State']['Name']
                platform_type = next((info['PlataformType'] for info in teste if info['Id'] == instance_id), 'Unknown')
                os_type = next((info['OperationSystem'] for info in teste if info['Id'] == instance_id), 'Unknown')
                
                instances_status.append({
                    'InstanceId': instance_id,
                    'ImageId': image_id,
                    'InstanceName': instance_name,
                    'SSMAgentInstalled': ssm_installed,
                    'Status': instance_status,
                    'InstanceFamily': instance_type_info['InstanceType'],
                    'vCPUs': instance_type_info['VCpuInfo']['DefaultVCpus'],
                    'Memory (MiB)': instance_type_info['MemoryInfo']['SizeInMiB'],
                    'AvailabilityZone': availability_zone,
                    'PlataformType': platform_type,
                    'OperationSystem': os_type,
                    'Volumes': volumes_info,
                    'AccountId': role_id
                })
        
        return instances_status
    
    def get_status_eks(self, region, role_id):
        client = region['client']
        all_eks_info = []
        instances_info = client.describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'terminated']}, {'Name': 'tag-key', 'Values': ['eks:nodegroup-name', 'eks:cluster-name']}])
        for reservation in instances_info['Reservations']:
            for instance in reservation['Instances']:
                instance_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'Name'), '-')
                nodegroup_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'eks:nodegroup-name'), '-')
                cluster_name = next((tag['Value'] for tag in instance['Tags'] if tag['Key'] == 'eks:cluster-name'), None)
                availability_zone = instance['Placement']['AvailabilityZone']
                instance_type_info = client.describe_instance_types(InstanceTypes=[instance['InstanceType']])['InstanceTypes'][0] 
                
                if cluster_name:
                    all_eks_info.append({
                        'ClusterName': cluster_name,
                        'NodeGroupName': nodegroup_name,
                        'NodeName': instance_name,
                        'InstanceFamily': instance_type_info['InstanceType'],
                        'vCPUs': instance_type_info['VCpuInfo']['DefaultVCpus'],
                        'Memory (MiB)': instance_type_info['MemoryInfo']['SizeInMiB'],
                        'AvailabilityZone': availability_zone,
                        'AccountId': role_id
                    })
                    
        return all_eks_info
    
    def get_status_ebs(self, region, role_id):
        client = region['client']
        volumes_status = []
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
                'AccountId': role_id
            })
            
        total_size = sum([volume['Size (GiB)'] for volume in volumes_status])
        
        volumes_status.append({
            'VolumeName': 'Total',
            'Size (GiB)': total_size
        })
        
        if total_size > 0:
            return volumes_status
        else:
            return None
        
    def get_status_efs(self, region, role_id):
        client = region['client_efs']
        all_efs_info = []
        file_systems = client.describe_file_systems()
        
        for file_system in file_systems['FileSystems']:
            all_efs_info.append({
                'Name': file_system.get('Name', None),
                'FileSystemId': file_system.get('FileSystemId', None),
                'SizeInBytes': file_system.get('SizeInBytes', {}).get('Value', None),
                'LifeCycleState': file_system.get('LifeCycleState', None),
                'AvailabilityZone': file_system.get('AvailabilityZoneName', None),
                'AccountId': role_id
                })
                
        return all_efs_info
    
    def get_status_fsx(self, region, role_id):
        client = region['client_fsx']
        all_fsx_info = []
        volumes = client.describe_file_systems()
        
        for volume in volumes['FileSystems']:
            
            all_fsx_info.append(
                {
                'FileSystemId': volume.get('FileSystemId', None),
                'OwnerId': volume.get('OwnerId', None),
                'FileSystemType': volume.get('FileSystemType', None),
                'Size': volume.get('StorageCapacity', None),
                'StorageType': volume.get('StorageType', None),
                'Lifecycle': volume.get('Lifecycle', None),
                'AccountId': role_id
                })

        return all_fsx_info

    def get_status_rds(self, region, role_id):
        client = region['client_rds']
        all_rds_info = []
        instances = client.describe_db_instances()
        
        for instance in instances['DBInstances']:
            iops = instance.get('Iops')
            
            all_rds_info.append(
                {
                'DBInstanceIdentifier': instance['DBInstanceIdentifier'],
                'Engine': instance['Engine'],
                # 'vCPUs': instanceq['ProcessorFeatures'],
                'EngineVersion': instance['EngineVersion'],
                'AvailabilityZone': instance['AvailabilityZone'],
                'AllocatedStorage': instance['AllocatedStorage'],
                'DBInstanceStatus': instance['DBInstanceStatus'],
                'DBInstanceType': instance.get('DBInstanceClass'),
                'Iops' : iops if iops else '-',
                'AccountId': role_id
                } 
                ) 
                
        return all_rds_info
    
    def get_status_docdb(self, region, role_id):
        client = region['client_doc_db']
        all_docdb_info = []
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
                    'AccountId': role_id
                    }
            )

        return all_docdb_info
    
    def get_status_dynamodb(self, region, role_id):
        client = region['client_dynamodb']
        tables_list = []
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
                    'AccountId': role_id
                    })
        return tables_list
    
    def get_status_apigw(self, region, role_id):
        client = region['client_apigateway']
        all_apigateway_info = []
        apis = client.get_rest_apis()
        
        for api in apis['items']:
            
            all_apigateway_info.append(
                {
                    "name": api["name"],
                    "Id": api["id"],
                    'version': api.get('version', '-'),
                    'endpoint': api['endpointConfiguration']['types'],
                    'description': api.get('description', '-'),
                    'AccountId': role_id
                    }
            )
                
        return all_apigateway_info
    
    def get_status_s3(self, region, role_id):
        client = region['client_s3']
        s3_info = []
        buckets = client.list_buckets()
    
        for bucket in buckets['Buckets']:
            creation = str(bucket['CreationDate'])
    
            # Obtém o nome do bucket
            bucket_name = bucket['Name']
    
            try:
                # Obtém a lista de objetos no bucket
                response = client.list_objects_v2(Bucket=bucket_name)
                objects = response.get('Contents', [])
    
                if objects:
                    # Calcula o tamanho total do bucket
                    total_size = sum(obj['Size'] for obj in objects)
                    total_size_mb = total_size / (1024 * 1024)
                else: 
                    total_size_mb = 0
    
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'AccessDenied':
                    total_size_mb = '-'
                else:
                    # Trate qualquer outra exceção que possa ocorrer
                    total_size_mb = 'Erro ao obter o tamanho'
    
            s3_info.append({
                'Name': bucket_name,
                'CreationDate': creation,
                'StorageUsageMB': total_size_mb,
                'AccountId': role_id
            })
    
        return s3_info

    def exec_ec2(self):
        combined_data_ec2 = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                ec2_status = self.get_status_ec2(region, id)  # Passa o ID da função assumida como argumento
    
                if ec2_status:
                    file_path = f'/tmp/ec2 - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(ec2_status, f, indent=4)
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_ec2 = pd.concat([combined_data_ec2, data])
    
        return combined_data_ec2
        
    def exec_ebs(self):
        combined_data_ebs = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                ebs_status = self.get_status_ebs(region, id)  # Passa o ID da função assumida como argumento
    
                if ebs_status:
                    file_path = f'/tmp/ebs - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(ebs_status, f, indent=4)
    
                    lista_de_arquivos.append(f'ebs - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_ebs = pd.concat([combined_data_ebs, data])
    
        return combined_data_ebs
    
    def exec_efs(self):
        combined_data_efs = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                efs_status = self.get_status_efs(region, id)  # Passa o ID da função assumida como argumento
    
                if efs_status:
                    file_path = f'/tmp/efs - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(efs_status, f, indent=4)
    
                    lista_de_arquivos.append(f'efs - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_efs = pd.concat([combined_data_efs, data])
    
        return combined_data_efs
    
    def exec_fsx(self):
        combined_data_fsx = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                fsx_status = self.get_status_fsx(region, id)  # Passa o ID da função assumida como argumento
    
                if fsx_status:
                    file_path = f'/tmp/fsx - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(fsx_status, f, indent=4)
    
                    lista_de_arquivos.append(f'fsx - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_fsx = pd.concat([combined_data_fsx, data])
    
        return combined_data_fsx
    
    def exec_eks(self):
        combined_data_eks = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                eks_status = self.get_status_eks(region, id)  # Passa o ID da função assumida como argumento
    
                if eks_status:
                    file_path = f'/tmp/eks - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(eks_status, f, indent=4)
    
                    lista_de_arquivos.append(f'eks - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_eks = pd.concat([combined_data_eks, data])
    
        return combined_data_eks
    
    def exec_rds(self):
        combined_data_rds = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                rds_status = self.get_status_rds(region, id)  # Passa o ID da função assumida como argumento
    
                if rds_status:
                    file_path = f'/tmp/rds - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(rds_status, f, indent=4)
    
                    lista_de_arquivos.append(f'rds - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_rds = pd.concat([combined_data_rds, data])
    
        return combined_data_rds
        
    def exec_docdb(self):
        combined_data_doc = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                doc_status = self.get_status_docdb(region, id)  # Passa o ID da função assumida como argumento
    
                if doc_status:
                    file_path = f'/tmp/doc - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(doc_status, f, indent=4)
    
                    lista_de_arquivos.append(f'doc - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_doc = pd.concat([combined_data_doc, data])
    
        return combined_data_doc
    
        
    def exec_dynamodb(self):
        combined_data_dynamo = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items(): 
                dynamo_status = self.get_status_dynamodb(region, id)  # Passa o ID da função assumida como argumento
    
                if dynamo_status:
                    file_path = f'/tmp/dynamo - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(dynamo_status, f, indent=4)
    
                    lista_de_arquivos.append(f'dynamo - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_dynamo = pd.concat([combined_data_dynamo, data])
    
        return combined_data_dynamo
    
    def exec_apigateway(self):
        combined_data_apigw = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                apigw_status = self.get_status_apigw(region, id)  # Passa o ID da função assumida como argumento
    
                if apigw_status:
                    file_path = f'/tmp/apigw - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(apigw_status, f, indent=4)
    
                    lista_de_arquivos.append(f'apigw - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_apigw = pd.concat([combined_data_apigw, data])
    
        return combined_data_apigw
    
    def exec_s3(self):
        combined_data_s3 = pd.DataFrame()  # DataFrame para combinar os dados de todos os arquivos
    
        for id, regions in self.regions.items():
            for region_name, region in regions.items():
                s3_status = self.get_status_s3(region, id)  # Passa o ID da função assumida como argumento
    
                if s3_status:
                    file_path = f'/tmp/S3 - {id} - {region_name}.json'
                    with open(file_path, 'w') as f:
                        json.dump(s3_status, f, indent=4)
    
                    lista_de_arquivos.append(f'S3 - {id} - {region_name}.json')
    
                    # Lê o arquivo JSON e adiciona os dados ao DataFrame combinado
                    with open(file_path, 'r') as f:
                        data = pd.read_json(f)
                        combined_data_s3 = pd.concat([combined_data_s3, data])
    
        return combined_data_s3 

import concurrent.futures

def lambda_handler(event, context):  
    data = date.today()
    data_hoje_formatada = data.strftime("%d-%m-%Y")
    inventario = AWSInventario()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(inventario.exec_ec2),
                  executor.submit(inventario.exec_eks),
                  executor.submit(inventario.exec_ebs),
                  executor.submit(inventario.exec_efs),
                  executor.submit(inventario.exec_fsx),
                  executor.submit(inventario.exec_s3),
                  executor.submit(inventario.exec_dynamodb),
                  executor.submit(inventario.exec_docdb),
                  executor.submit(inventario.exec_rds),
                  executor.submit(inventario.exec_apigateway)]
        
        combined_data = [future.result() for future in futures]

    writer = pd.ExcelWriter('/tmp/InvFull.xlsx', engine='xlsxwriter')
    
    sheet_names = ['EC2', 'EKS', 'EBS', 'EFS', 'FSX', 'S3', 'DynamoDB', 'DocumentDB', 'RDS', 'ApiGateWay']
    
    for i, data in enumerate(combined_data):
        data.to_excel(writer, sheet_name=sheet_names[i], index=False)

    writer.save()
    
    
    import openpyxl
    from openpyxl.styles import NamedStyle, Font
    
    # ...
    
    # Código anterior para gerar os dados e salvar o arquivo Excel
    
    # Carregar o arquivo Excel gerado
    workbook = openpyxl.load_workbook('/tmp/InvFull.xlsx')
    
    # Definir o estilo "Blue Table Medium 2"
    blue_table_medium_2 = NamedStyle(name='blue_table_medium_2')
    blue_table_medium_2.font = Font(bold=True)
    blue_table_medium_2.header = True
    blue_table_medium_2.tableStyleInfo = "TableStyleMedium2"
    
    # Aplicar o estilo a todas as planilhas
    for sheet_name in sheet_names:
        worksheet = workbook[sheet_name]
        worksheet.append([])  # Adicionar uma linha em branco no final
        worksheet.append([])  # Adicionar uma linha em branco no final
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column].width = adjusted_width
    
        worksheet.append([])  # Adicionar uma linha em branco no final
    
        for row in worksheet.iter_rows(min_row=1, max_row=1):
            for cell in row:
                cell.style = blue_table_medium_2
    
    # Salvar o arquivo Excel com as alterações
    workbook.save('/tmp/InvFull_formatted.xlsx')

    s3 = boto3.client('s3')
    bucket_name = 'bucket_name' 
    s3.upload_file('/tmp/InvFull_formatted.xlsx', bucket_name, f'InventarioFullAWS-{data_hoje_formatada}.xlsx') 

    return {
        'statusCode': 200,
        'body': {
            'uploaded_files': 'Inventário-Auto-AWS criado com sucesso'
        }
     } 
