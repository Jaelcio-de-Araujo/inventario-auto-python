<h1 align="center"> Inventário Auto AWS </h1>

Este projeto tem como objetivo a criação de uma função lambda que retorna um inventário de recursos da Amazon Web Services (AWS)
Os recursos mapeados por essa automação são: EC2, EKS, EBS, EFS, FSX, S3, DynamoDB, DocumentDB, RDS e ApiGateWay

## Início

Primeiro clone o repositório

- git clone https://github.com/joaolfms/inventario-auto.git

O script foi escrito em Python 3 e necessita das seguintes bibliotecas: boto3, json, pandas, datetime e botocore

Para isso instale os requirements em uma pasta vazia chamada python

- mkdir python
- cd python
- pip install -r requirements.txt -t .

Depois dos requirements instalados na pasta python comprima a pasta python

- zip -r python.zip python

## Criando a role para a função lambda

## Como usar

Após configurar a função Lambda, basta acioná-la manualmente ou agendar a execução conforme necessário.
Caso esteja usando através da CLI basta executar o arquivo no terminal, exemplo: "python3 inventario-auto.py"

O resultado da execução será um arquivo Excel salvo no bucket S3 configurado, contendo informações sobre as ferramentas da AWS mencionadas anteriormente.

## Desenvolvedor
Este projeto foi desenvolvido por **João Lucas Férras da Motta dos Santos**.

## Contribuição

Este projeto é de código aberto e contribuições são bem-vindas. Para contribuir, siga os seguintes passos:

- Fork o repositório do projeto.
- Crie uma branch para sua nova feature ou correção de bug: git checkout -b nome-da-feature-ou-bugfix
- Faça as mudanças necessárias e faça commit das mudanças: git commit -am 'descrição do commit'
- Push para a branch: git push origin nome-da-feature-ou-bugfix
- Crie um Pull Request para o repositório original.
- Aguarde a revisão do seu Pull Request.
