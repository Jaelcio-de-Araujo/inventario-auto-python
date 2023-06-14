# Inventário Auto AWS


**Este documento tem como objetivo apresentar a automação desenvolvida para coletar dados de recursos da AWS e entregar, de forma automatizada, um arquivo contendo informações sobre cada recurso, além de fornecer instruções sobre como acessar a planilha gerada. A solução foi implementada utilizando um script Python, fazendo uso das bibliotecas Pandas, XlsxWriter e Boto3 (SDK da AWS).**

**A execução do script ocorre por meio de uma função Lambda, acionada uma vez por mês pelo Amazon EventBridge. Essa função tem visibilidade para todas as contas configuradas, permitindo que o script obtenha informações dos recursos presentes nas regiões selecionadas, sa-east-1 (São Paulo) e us-east-1 (N-Virginia). Caso algum recurso não seja encontrado, os dados correspondentes não serão incluídos na planilha.**

**A solução automatizada garante a coleta eficiente de informações em todas as contas e regiões selecionadas, proporcionando uma visão abrangente dos recursos existentes na infraestrutura da AWS. O uso das bibliotecas Pandas e XlsxWriter permite a manipulação e organização dos dados de forma adequada, enquanto o Boto3 facilita a integração com os serviços da AWS.**

**Para acessar a planilha gerada, siga as etapas abaixo:**

- Após a execução da função Lambda, aguarde até que o processamento seja concluído. Isso pode levar alguns minutos, dependendo do número de contas e recursos.
- Acesse o serviço do Amazon S3, que é onde o arquivo da planilha é armazenado.
- Navegue para o bucket (repositório) especificado na configuração da função Lambda.
- Procure o arquivo InventarioInventarioFullAWS-data-da-ultima-execução.
- Baixe o arquivo da planilha para o seu dispositivo ou visualize-o diretamente no navegador, se houver suporte.

**Essa solução automatizada simplifica o processo de coleta de dados da AWS, proporcionando uma visão abrangente e organizada dos recursos utilizados nas contas e regiões configuradas. A execução periódica agendada via EventBridge garante a atualização regular das informações, facilitando a análise e o monitoramento da infraestrutura.**

## Início

**Primeiro clone o repositório**

```bash
git clone https://github.com/joaolfms/inventario-auto.git
```

**O script foi escrito em Python 3 e necessita das seguintes bibliotecas: boto3, json, pandas, datetime e botocore**

**Para isso instale os requirements em uma pasta vazia chamada python**

```zsh
mkdir python

pip install -r requirements.txt -t ./python
```

**Depois dos requirements instalados na pasta python comprima a pasta python**

```bash
zip -r python.zip python
```

## Criando a role para a função lambda

**Na conta principal em que a função lambda funcionará vá até o painel do IAM no console da AWS**

* Vá em roles
* Create role
* Em trusted entity selecione a opção AWS service
* Em Common use cases marque a opção lambda depois clique em next
* Agora clique em create policy
* Em policy editor selecione a opção json
* Copie o conteúdo do arquivo inventario.json e cole no editor (Não esqueça de trocar o id das contas e o nome do bucket para os seus)
* Defina o nome da policy 'inventario_role', decrição e tags são opcionais
* Attach a policy criada a role

**A função lambda usa o STS do boto3 para assumir a role da função e executar o script**

* Na role vá até Trust relationships da role 'inventario_role'
* Em edit trust policy adicione o conteúdo do aquivo Trust.json depois em update policy **Obs.: Essa Trust relationships Policy deve conter o ARN da própria role ('inventario_role')**

## Cross Account

**Para fazer com que a função itere também sobre outras contas dentro de uma organization é necessário seguir os seguintes passos:**

* Copie a policy da role criada anteriormente
* crie a role na conta que deseja fazer o Cross Account e cole a policy (Precisa ser igual as roles) e dê o nome 'inventario_cross'
* Em Trust relationships vá em edit trust policy e cole o conteúdo de trust.json (Nesse caso o ARN precisa ser igual ao da role da conta principal 'inventario_role')
* Na role 'inventario_role' na conta principal, vá em add permissions e clique em Create inline policy
* Copie o conteúdo de cross-acount.json e cole na inline policy (Note que o ARN deve ser igual ao da role 'inventario_cross')
* Repita os passos anteriores para adicionar o cross account em outras contas (Preste atenção nos ARNs para não confundir)

## Criando a função lambda

**No console AWS da conta principal vá até lambda**

* Create function
* Escolha o nome da função
* Em runtime escolha Python 3.9
* Em Architeture mantenha em x86_64
* Em Permissions clique em Change default execution role
* Use an existing role
* Escolha a role 'inventario_role'
* Create function

**Abra a função criada e copie o código de inventario-auto.py e cole na função**

* No painel do lambda vá até layers
* Clique em Create layer
* Dê um nome a Layer, descrição é opcional
* Faça Upload do arquivo python.zip criado no início
* Architeture x86_64
* Runtimes python 3.9
* Create

**Na função lambda criada role até o final da página**

* Clique em add layers na opção layers
* Deixe a opção AWS layers marcada
* Escolha a Layer AWSSDKPandas-Python3.9
* Em version escolha a última versão
* Depois clique em add
* Role para baixo novamente e adicione outra layer
* Agora seleciona a opção Custom layer
* Selecione a Layer que criamos e a versão
* Clique em add

**Pronto, agora seu inventário auto está implementado, não esqueça de editar os ids das contas na linha 11 do código**

## Desenvolvedor

Este projeto foi desenvolvido por  **João Lucas Férras da Motta dos Santos** .

## Contribuição

Este projeto é de código aberto e contribuições são bem-vindas. Para contribuir, siga os seguintes passos:

* Fork o repositório do projeto.
* Crie uma branch para sua nova feature ou correção de bug: git checkout -b nome-da-feature-ou-bugfix
* Faça as mudanças necessárias e faça commit das mudanças: git commit -am 'descrição do commit'
* Push para a branch: git push origin nome-da-feature-ou-bugfix
* Crie um Pull Request para o repositório original.
* Aguarde a revisão do seu Pull Request.
