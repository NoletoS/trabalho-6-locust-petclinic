### Resultados medidos

Valores são médias aritméticas das 10 repetições por configuração. Cada rodada tem 6 min, dos quais os primeiros 60 s foram descartados; vazão usa 300 s como denominador. `req/s` inclui respostas com erro; `req/s OK` conta apenas respostas bem-sucedidas. P95 é calculado em cada rodada pelo posto mais próximo e depois promediado.

| Perfil | Cenário | Usuários | Média ms | P95 ms | req/s | req/s OK | Req. | Falhas % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| leitura | A | 30 | 23.14 | 56.63 | 29.06 | 28.35 | 8718.0 | 2.43 |
| leitura | B | 80 | 124.24 | 579.12 | 70.86 | 68.07 | 21257.3 | 3.73 |
| leitura | C | 150 | 1056.64 | 2812.97 | 73.49 | 67.65 | 22047.8 | 6.59 |
| escrita | A | 30 | 69.29 | 312.45 | 27.86 | 26.61 | 8357.1 | 4.41 |
| escrita | B | 80 | 1159.26 | 6296.72 | 36.93 | 23.90 | 11078.2 | 34.88 |
| escrita | C | 150 | 545.41 | 4571.64 | 96.45 | 11.37 | 28934.4 | 88.26 |

| Perfil | Cenário | Gateway % | Customers % | Vets % |
| --- | --- | --- | --- | --- |
| leitura | A | 11.43 | 58.11 | 1.98 |
| leitura | B | 34.27 | 301.69 | 4.21 |
| leitura | C | 41.50 | 443.73 | 4.00 |
| escrita | A | 12.47 | 133.66 | 2.05 |
| escrita | B | 20.63 | 281.71 | 2.77 |
| escrita | C | 23.83 | 155.38 | 1.29 |

#### Operações

| Perfil | Cenário | Operação | Peso observado % | Média ms | P95 ms | Falhas % |
| --- | --- | --- | --- | --- | --- | --- |
| leitura | A | GET /owners | 45.21 | 38.35 | 62.80 | 2.43 |
| leitura | A | GET /owners/{id} | 34.92 | 7.00 | 9.55 | 2.46 |
| leitura | A | GET /vets | 14.93 | 7.53 | 10.47 | 2.44 |
| leitura | A | POST /owners | 4.94 | 45.05 | 55.72 | 2.25 |
| leitura | B | GET /owners | 45.14 | 209.06 | 743.04 | 3.75 |
| leitura | B | GET /owners/{id} | 34.84 | 68.01 | 363.48 | 3.80 |
| leitura | B | GET /vets | 14.99 | 9.18 | 16.23 | 3.46 |
| leitura | B | POST /owners | 5.02 | 97.25 | 391.42 | 3.87 |
| leitura | C | GET /owners | 44.92 | 1374.57 | 3033.20 | 6.61 |
| leitura | C | GET /owners/{id} | 35.10 | 1091.55 | 2557.16 | 6.52 |
| leitura | C | GET /vets | 15.07 | 9.93 | 19.60 | 6.64 |
| leitura | C | POST /owners | 4.91 | 1110.67 | 2593.78 | 6.75 |
| escrita | A | GET /owners | 20.07 | 238.60 | 489.94 | 4.57 |
| escrita | A | GET /owners/{id} | 19.75 | 10.19 | 16.39 | 4.29 |
| escrita | A | GET /vets | 20.07 | 7.74 | 11.79 | 4.30 |
| escrita | A | POST /owners | 40.11 | 44.70 | 59.85 | 4.45 |
| escrita | B | GET /owners | 19.98 | 2143.39 | 9710.77 | 38.47 |
| escrita | B | GET /owners/{id} | 20.21 | 1207.56 | 6102.54 | 34.33 |
| escrita | B | GET /vets | 20.04 | 8.84 | 18.55 | 33.36 |
| escrita | B | POST /owners | 39.77 | 1220.92 | 6008.46 | 34.12 |
| escrita | C | GET /owners | 19.94 | 775.11 | 7277.13 | 89.93 |
| escrita | C | GET /owners/{id} | 20.05 | 616.25 | 5069.28 | 88.42 |
| escrita | C | GET /vets | 19.92 | 5.09 | 9.67 | 86.29 |
| escrita | C | POST /owners | 40.09 | 664.07 | 5246.24 | 88.33 |

![Tempo médio](graphs/response_mean.png)
![P95](graphs/response_p95.png)
![Vazão](graphs/throughput.png)
![Vazão bem-sucedida](graphs/successful_throughput.png)
![Falhas](graphs/failures.png)
![CPU](graphs/cpu.png)
![P95 por operação](graphs/operations_p95.png)

### Respostas às questões

1. **Usuários e tempo de resposta:** em leitura, a média subiu de 23.14 ms (A) para 124.24 ms (B) e 1056.64 ms (C). Em escrita, foi 69.29 ms (A), 1159.26 ms (B) e 545.41 ms (C). A queda aparente de B para C em escrita ocorre junto de 88.26% de falhas; respostas de erro rápidas reduzem a média, sem indicar melhora do serviço.
2. **Maior vazão:** leitura, pela média de req/s dos três cenários (57.80 em leitura; 53.74 em escrita). Em requisições bem-sucedidas/s, leitura também liderou (54.69 contra 20.63). O pico bruto de 96.45 req/s em escrita C contém muitas falhas; só 11.37 req/s tiveram sucesso.
3. **Maior degradação:** GET /owners no perfil escrita, com aumento de 6787.19 ms no P95 médio de A para C (14.85×). A comparação completa por operação está em `results/operations.csv`.
4. **CPU:** de A para C, api-gateway: 11.43→41.50% em leitura e 12.47→23.83% em escrita; customers-service: 58.11→443.73% em leitura e 133.66→155.38% em escrita; vets-service: 1.98→4.00% em leitura e 2.05→1.29% em escrita. CPU do Docker pode superar 100% em múltiplos núcleos; é porcentagem de núcleo, não fração do limite da máquina. A CPU de customers em escrita C ficou abaixo de B ao mesmo tempo que a taxa de falhas aumentou muito; isso não demonstra ganho de eficiência.
5. **Maior taxa de falhas:** escrita / cenário C, 88.26%.

### Conclusões

Nesta campanha, **leitura** teve a maior vazão média e **leitura** a maior vazão bem-sucedida. A maior degradação do P95 entre A e C foi GET /owners em escrita, com aumento de 6787.19 ms. A maior taxa de falhas foi escrita / cenário C, 88.26%. Em escrita C, apenas 11.37 das 96.45 req/s médias tiveram sucesso. Não se deve interpretar o menor tempo médio desse cenário como melhora do atendimento.

Os logs do Locust registram HTTP 405 em GETs e HTTP 503 em POSTs. O gateway também registrou períodos sem instâncias disponíveis de `customers-service`; isso sustenta parte dos 503, mas os registros atuais não permitem atribuir com segurança todos os 405 a uma causa única. Portanto, as conclusões sobre degradação descrevem a **pilha implantada neste ambiente**, não isolam o desempenho interno de cada microsserviço. Os tempos de resposta incluem falhas; a vazão bem-sucedida ajuda a distinguir rapidez de erro de capacidade útil.

Os CSVs de cada execução em `results/raw/` são a evidência bruta. Os números refletem este ambiente e esta ordem de rodadas; criação de proprietários aumenta o tamanho da base dentro de cada rodada. Variações entre repetições e serviços concorrentes no host também limitam a generalização.
