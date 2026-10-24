# Ambiente experimental

Condições registradas durante a campanha:

| Campo | Valor medido |
| --- | --- |
| Data/hora e fuso da campanha | 22 a 23/10/2026, America/Sao_Paulo; início e fim de cada rodada registrados em `metadata.json` |
| Sistema operacional | Microsoft Windows 11 Home 10.0.22631 |
| CPU física/lógica e RAM do host | AMD Ryzen 7 5700U; 8 núcleos, 16 threads; 11,35 GB visíveis |
| Recursos atribuídos ao Docker | 16 CPUs e 5.870.555.136 bytes (~5,47 GiB) de memória |
| Docker Engine e Compose | Engine 29.5.2; Compose v5.1.4 |
| Python e Locust | Python 3.12.14; Locust 2.32.10 |
| Commit do Compose PetClinic | `1d76b00d683e86b62867a6bf59530f8ab301244f` |
| Estado inicial da base e procedimento de restauração | HSQLDB em memória; `docker compose restart customers-service` antes de cada rodada após a primeira, com confirmação de 10 proprietários. A pré-verificação cria um proprietário. Os metadados mostram 11 IDs conhecidos em 59 rodadas e 12 na primeira (`leitura_A_01`), executada antes da inclusão da rotina de restauração. Tentativas interrompidas foram refeitas; seus arquivos parciais foram removidos na limpeza após a campanha. |
| Outros processos relevantes | Quatro contêineres RabbitMQ de outro projeto estavam ativos no início. Não há registro do estado deles em todas as rodadas; podem ter interferido nas medições. |
| Observações sobre falhas e outliers | Em escrita C, a falha média foi 88,26%; os logs do Locust mostram HTTP 405 em GETs e 503 em POSTs. O gateway registrou períodos sem instâncias disponíveis de `customers-service`. A origem de todos os 405 não foi estabelecida. A vazão bruta inclui falhas e deve ser lida junto da vazão bem-sucedida. |

## Imagens efetivamente executadas

O Compose foi obtido no commit acima, mas usa imagens `latest` pré-construídas. Estes são os digests baixados em 22/10/2026; a implementação contida nas imagens pode anteceder o commit do arquivo Compose. As quatro rotas foram confirmadas por chamadas HTTP no ambiente em execução antes da carga.

O Docker Desktop 4.76.0 inicialmente falhou ao criar sockets Unix locais antigos. Os sockets foram preservados com sufixo `.stale-20261022`, e `EnableDockerAI` foi desativado na configuração local para permitir a inicialização. Isso não altera os serviços PetClinic. A configuração original foi copiada para `docker-settings-backup.json`, arquivo local ignorado pelo Git.

| Serviço | Digest |
| --- | --- |
| config-server | `sha256:db14626a92afda51963a29804fe24329b7711467ffdc7dc2157fe800abc3f756` |
| discovery-server | `sha256:c3cb50137cf7f2f61ac7f3f878f93b79a3b71213360a0d4550a4f5ab4418c342` |
| customers-service | `sha256:ab1181fed9b1c23a74a442c1c1625f1ab34b4e0e928192cb5db77eef3f75b14a` |
| vets-service | `sha256:963f480587e365b7ef17fdbcce5267ac3aa3436f649852cc7eb4f85da86abab4` |
| visits-service | `sha256:307ae223b722d13b7a0e35ef34e93352ab118687d9a0e189565392244031a1c7` |
| api-gateway | `sha256:250c96946936d623d4ded3e1987fd76d61a66a3125913e5eee6556f2a80d5862` |
